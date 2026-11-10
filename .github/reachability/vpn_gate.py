#!/usr/bin/env python3
"""Manual, review-only measurements through Russian VPN Gate volunteer exits.

Only RU VPN Gate entries are selected. Downloaded OpenVPN profiles are never
executed directly: a minimal client profile is rebuilt from a strict allowlist,
using the API-advertised public IP, a validated remote port/protocol and inline
CA material only. A host firewall kill-switch blocks non-tunnel egress while
the tunnel is active. No GeoIP input, builder, release or DIRECT policy is
modified.
"""
from __future__ import annotations

import argparse
import base64
import collections
import csv
import datetime as dt
import ipaddress
import io
import json
import pathlib
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import runner

VPN_GATE_API = "https://www.vpngate.net/api/iphone/"
IP_INFO_URLS = (
    "https://ipwho.is/",
    "https://ipapi.co/json/",
    "https://ipinfo.io/json",
)
RIPESTAT_NETWORK_INFO = "https://stat.ripe.net/data/network-info/data.json"
USER_AGENT = "Geoip-ru-server-vpn-gate-validation/1.0"
PROVIDER_FIELDS = [
    "SOURCE", "SERVER_HOSTNAME", "SERVER_IP", "SERVER_COUNTRY",
    "SERVER_ASN", "SERVER_PREFIX", "SERVER_ORG", "SERVER_PTR",
    "SERVER_GEOIP_CATEGORY", "SERVER_GEOIP_RU_PREFIX",
    "VPN_SCORE", "VPN_PING_MS", "VPN_SPEED_BPS", "VPN_SESSIONS",
    "VPN_UPTIME", "ERROR", "EXIT_IP", "EXIT_COUNTRY", "EXIT_ASN",
    "EXIT_PREFIX", "EXIT_ORG", "EXIT_GEOIP_CATEGORY",
    "EXIT_GEOIP_RU_PREFIX", "CONNECTION_RESULT", "TARGETS_TESTED",
]
MEASUREMENT_FIELDS = [
    "SOURCE", "OBSERVED_AT", "SERVER_HOSTNAME", "SERVER_IP",
    "SERVER_ASN", "SERVER_ORG", "EXIT_IP", "EXIT_COUNTRY",
    "EXIT_ASN", "EXIT_ORG", "EXIT_GEOIP_CATEGORY", "EXIT_GEOIP_RU_PREFIX",
    "TARGET_ID", "TARGET_DOMAIN", "DNS_A_RESULT", "DNS_A_ADDRESSES",
    "DNS_A_RU_PREFIXES", "DNS_AAAA_RESULT", "DNS_AAAA_ADDRESSES",
    "DNS_AAAA_RU_PREFIXES", "HTTPS_RESULT", "HTTP_STATUS", "ERROR",
]
CANDIDATE_FIELDS = [
    "CANDIDATE_TYPE", "SERVER_HOSTNAME", "SERVER_IP", "EXIT_IP",
    "EXIT_COUNTRY", "EXIT_ASN", "EXIT_ORG", "GEOIP_CATEGORY",
    "MATCHED_RU_PREFIX", "REASON", "REVIEW_POLICY",
]


class ProbeError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_bytes(url: str, timeout: int = 25) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.read(8_000_000)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProbeError(f"request failed for {urllib.parse.urlparse(url).netloc}: {exc}") from exc


def fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    try:
        payload = json.loads(fetch_bytes(url, timeout).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"invalid JSON from {urllib.parse.urlparse(url).netloc}") from exc
    if not isinstance(payload, dict):
        raise ProbeError(f"unexpected JSON object from {urllib.parse.urlparse(url).netloc}")
    return payload


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_vpngate_csv(text: str) -> list[dict[str, Any]]:
    """Parse the official CSV export; ignore malformed/non-RU/non-public rows."""
    lines = text.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines)
         if line.lstrip().startswith("#HostName,")),
        None,
    )
    if header_index is None:
        raise ValueError("VPN Gate CSV header '#HostName' was not found")
    header = next(csv.reader([lines[header_index].lstrip()[1:]]))
    header = [item.strip() for item in header]
    required = {
        "HostName", "IP", "Score", "Ping", "Speed", "CountryLong",
        "CountryShort", "NumVpnSessions", "Uptime", "OpenVPN_ConfigData_Base64",
    }
    if not required.issubset(set(header)):
        raise ValueError(f"VPN Gate CSV is missing columns: {sorted(required - set(header))}")

    reader = csv.DictReader(
        io.StringIO("\n".join(lines[header_index + 1:])),
        fieldnames=header,
    )
    servers: dict[str, dict[str, Any]] = {}
    for row in reader:
        if not row or not row.get("HostName") or row["HostName"].startswith(("*", "#")):
            continue
        if str(row.get("CountryShort") or "").strip().upper() != "RU":
            continue
        hostname = str(row.get("HostName") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", hostname):
            continue
        try:
            address = ipaddress.ip_address(str(row.get("IP") or "").strip())
        except ValueError:
            continue
        if address.version != 4 or not address.is_global:
            continue
        encoded = str(row.get("OpenVPN_ConfigData_Base64") or "").strip()
        if not encoded:
            continue
        try:
            config = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if len(config) > 64_000:
            continue
        try:
            parsed = inspect_openvpn_profile(config)
        except ValueError:
            continue
        servers[hostname] = {
            "hostname": hostname,
            "server_ip": str(address),
            "country_long": str(row.get("CountryLong") or "").strip(),
            "country_short": "RU",
            "score": parse_int(row.get("Score")),
            "ping_ms": parse_int(row.get("Ping")),
            "speed_bps": parse_int(row.get("Speed")),
            "vpn_sessions": parse_int(row.get("NumVpnSessions")),
            "uptime": str(row.get("Uptime") or "").strip(),
            "config": config,
            "profile": parsed,
        }
    return sorted(
        servers.values(),
        key=lambda item: (-item["score"], -item["speed_bps"], item["ping_ms"], item["hostname"]),
    )


def inspect_openvpn_profile(config: str) -> dict[str, Any]:
    """Extract only transport and inline trust material; never execute profile directives."""
    blocks: dict[str, str] = {}
    directives: list[list[str]] = []
    lines = config.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = re.fullmatch(r"<(ca|tls-auth|tls-crypt)>", line, re.IGNORECASE)
        if match:
            name = match.group(1).lower()
            end_tag = f"</{name}>"
            block_lines = [line]
            index += 1
            while index < len(lines) and lines[index].strip().lower() != end_tag:
                block_lines.append(lines[index])
                index += 1
            if index >= len(lines):
                raise ValueError(f"unterminated OpenVPN {name} block")
            block_lines.append(end_tag)
            if name in blocks:
                raise ValueError(f"duplicate OpenVPN {name} block")
            blocks[name] = "\n".join(block_lines)
        elif line and not line.startswith(("#", ";")):
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError:
                tokens = []
            if tokens:
                directives.append(tokens)
        index += 1

    remotes = [item for item in directives if item[0].lower() == "remote"]
    protocols = [item for item in directives if item[0].lower() == "proto"]
    if not remotes or len(remotes[0]) < 3 or not protocols or len(protocols[0]) < 2:
        raise ValueError("OpenVPN profile has no usable remote/proto")
    port = parse_int(remotes[0][2])
    if not 1 <= port <= 65535:
        raise ValueError("OpenVPN remote port is invalid")
    proto = protocols[0][1].lower()
    if proto in {"tcp", "tcp4", "tcp-client", "tcp4-client"}:
        proto = "tcp-client"
    elif proto in {"udp", "udp4"}:
        proto = "udp"
    else:
        raise ValueError("unsupported OpenVPN transport protocol")
    if "ca" not in blocks or "-----BEGIN CERTIFICATE-----" not in blocks["ca"]:
        raise ValueError("OpenVPN profile has no valid inline CA block")

    def selected_value(name: str) -> str:
        values = [item[1] for item in directives if item[0].lower() == name and len(item) == 2]
        if not values:
            return ""
        value = values[0]
        if not re.fullmatch(r"[A-Za-z0-9_.:+-]{1,80}", value):
            return ""
        return value

    key_direction = selected_value("key-direction")
    return {
        "port": port,
        "proto": proto,
        "cipher": selected_value("cipher"),
        "auth": selected_value("auth"),
        "key_direction": key_direction,
        "blocks": blocks,
    }


def build_safe_openvpn_config(server: dict[str, Any], auth_path: pathlib.Path) -> str:
    """Rebuild a minimal profile, replacing the untrusted remote and dropping scripts/plugins."""
    profile = server["profile"]
    lines = [
        "client",
        "dev tun",
        f"proto {profile['proto']}",
        f"remote {server['server_ip']} {profile['port']}",
        "nobind",
        "persist-key",
        "persist-tun",
        "remote-cert-tls server",
        "auth-user-pass " + str(auth_path),
        "auth-nocache",
        "resolv-retry infinite",
        "route-nopull",
        "redirect-gateway def1",
        "connect-retry 2 5",
        "verb 3",
        "mute 10",
        "data-ciphers AES-256-GCM:AES-128-GCM:AES-128-CBC",
    ]
    if profile["cipher"]:
        lines.extend([f"cipher {profile['cipher']}", f"data-ciphers-fallback {profile['cipher']}"])
    if profile["auth"]:
        lines.append(f"auth {profile['auth']}")
    if profile["key_direction"] and "tls-auth" in profile["blocks"]:
        lines.append(f"key-direction {profile['key_direction']}")
    for name in ("ca", "tls-auth", "tls-crypt"):
        if name in profile["blocks"]:
            lines.append(profile["blocks"][name])
    return "\n".join(lines) + "\n"


def parse_asn(value: Any) -> int:
    match = re.search(r"(?:AS)?(\d{1,10})", str(value or ""), re.IGNORECASE)
    return int(match.group(1)) if match else 0


def network_info(address: str) -> dict[str, Any]:
    url = RIPESTAT_NETWORK_INFO + "?" + urllib.parse.urlencode({"resource": address})
    try:
        payload = fetch_json(url)
        data = payload.get("data") or {}
        asns = data.get("asns") or []
        asn = parse_asn(asns[0]) if asns else 0
        return {"prefix": data.get("prefix") or "", "asn": asn}
    except ProbeError:
        return {"prefix": "", "asn": 0}


def ip_metadata(url: str | None = None) -> dict[str, Any]:
    """Identify the actual egress using two common public IP metadata responses."""
    errors: list[str] = []
    for endpoint in ((url,) if url else IP_INFO_URLS):
        try:
            payload = fetch_json(endpoint, timeout=15)
            connection = payload.get("connection") or {}
            address = str(payload.get("ip") or "").strip()
            parsed = ipaddress.ip_address(address)
            if not parsed.is_global:
                raise ProbeError("egress address is not globally routable")
            country = str(payload.get("country_code") or payload.get("country") or "").upper()
            org = str(connection.get("org") or connection.get("isp") or payload.get("org") or "").strip()
            asn = parse_asn(connection.get("asn") or payload.get("asn") or org)
            return {
                "ip": address,
                "country": country,
                "asn": asn,
                "org": org,
                "network_prefix": "",
                "source": urllib.parse.urlparse(endpoint).netloc,
            }
        except (ProbeError, ValueError) as exc:
            errors.append(str(exc))
    raise ProbeError("unable to verify VPN exit IP/country: " + "; ".join(errors[:2]))


def resolve_ptr(address: str) -> str:
    try:
        return socket.gethostbyaddr(address)[0]
    except (OSError, socket.herror, socket.gaierror):
        return ""


def run_command(args: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, input=input_text, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=check, timeout=15,
    )


class FirewallGuard:
    """Fail-closed OUTPUT policy: only OpenVPN transport and tun0 can egress."""
    def __init__(self, server_ip: str, proto: str, port: int):
        self.server_ip, self.proto, self.port = server_ip, proto, port
        self.ipv4_rules = ""
        self.ipv6_rules = ""

    def _restore(self) -> list[str]:
        restore_errors = []
        for command, rules in (("iptables-restore", self.ipv4_rules), ("ip6tables-restore", self.ipv6_rules)):
            try:
                run_command([command], input_text=rules)
            except (OSError, subprocess.SubprocessError) as exc:
                restore_errors.append(f"{command}: {exc}")
        return restore_errors

    def __enter__(self):
        self.ipv4_rules = run_command(["iptables-save"]).stdout
        self.ipv6_rules = run_command(["ip6tables-save"]).stdout
        try:
            run_command(["iptables", "-F", "OUTPUT"])
            run_command(["iptables", "-P", "OUTPUT", "DROP"])
            run_command(["iptables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"])
            run_command(["iptables", "-A", "OUTPUT", "-o", "tun+", "-j", "ACCEPT"])
            proto = "tcp" if self.proto == "tcp-client" else "udp"
            run_command([
                "iptables", "-A", "OUTPUT", "-d", self.server_ip,
                "-p", proto, "--dport", str(self.port), "-j", "ACCEPT",
            ])
            run_command(["ip6tables", "-F", "OUTPUT"])
            run_command(["ip6tables", "-P", "OUTPUT", "DROP"])
            run_command(["ip6tables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"])
        except BaseException:
            # __exit__ is not called when __enter__ fails; restore snapshots here.
            errors = self._restore()
            if errors:
                raise ProbeError("firewall setup failed and restore was incomplete: " + "; ".join(errors))
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        restore_errors = self._restore()
        if restore_errors and exc_type is None:
            raise ProbeError("failed to restore host firewall: " + "; ".join(restore_errors))


class ResolverGuard:
    """Use a public resolver only while the default route is verified through tun0."""
    def __init__(self):
        self.path = pathlib.Path("/etc/resolv.conf")
        self.original = b""

    def __enter__(self):
        self.original = self.path.read_bytes()
        self.path.write_text("nameserver 1.1.1.1\noptions timeout:2 attempts:2\n", encoding="ascii")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.path.write_bytes(self.original)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def wait_for_tunnel(process: subprocess.Popen, timeout: int) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ProbeError(f"OpenVPN exited early with code {process.returncode}")
        result = run_command(["ip", "-4", "route", "get", "1.1.1.1"], check=False)
        if result.returncode == 0:
            match = re.search(r"\bdev\s+(tun\S*)", result.stdout)
            if match:
                return match.group(1)
        time.sleep(1)
    raise ProbeError("OpenVPN tunnel did not install an IPv4 default route before timeout")


def resolve_domain(domain: str, family: int, timeout: int) -> tuple[str, list[str], str]:
    try:
        socket.setdefaulttimeout(timeout)
        infos = socket.getaddrinfo(domain, 443, family, socket.SOCK_STREAM)
        addresses = sorted({item[4][0] for item in infos})
        return ("DNS_ANSWER" if addresses else "DNS_NO_ANSWER", addresses, "")
    except socket.gaierror as exc:
        return "DNS_ERROR", [], str(exc)
    except OSError as exc:
        return "DNS_ERROR", [], str(exc)


def https_head(domain: str, port: int, path: str, timeout: int) -> tuple[str, int | None, str]:
    url = f"https://{domain}:{port}{path}"
    request = urllib.request.Request(
        url, method="HEAD",
        headers={"User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "close"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            return "HTTP_RESPONSE", int(response.status), ""
    except urllib.error.HTTPError as exc:
        # Any HTTP response (including 403/5xx) proves a TCP/TLS/HTTP exchange,
        # not that the service is healthy or that content is unfiltered.
        return "HTTP_RESPONSE", int(exc.code), ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return "INCONCLUSIVE", None, str(exc)[:300]


def test_target(target: dict[str, Any], exit_info: dict[str, Any], networks: dict[str, Any], timeout: int) -> dict[str, Any]:
    a_result, a_addresses, a_error = resolve_domain(target["domain"], socket.AF_INET, timeout)
    aaaa_result, aaaa_addresses, aaaa_error = resolve_domain(target["domain"], socket.AF_INET6, timeout)
    https_result, http_status, https_error = https_head(
        target["domain"], int(target["port"]), target["path"], timeout
    )
    address_mappings = {
        address: runner.map_address(address, networks)
        for address in sorted(set(a_addresses + aaaa_addresses))
    }
    a_ru = sorted({prefix for address in a_addresses
                   for category, prefix in [address_mappings[address]] if category == "RU"})
    aaaa_ru = sorted({prefix for address in aaaa_addresses
                      for category, prefix in [address_mappings[address]] if category == "RU"})
    errors = [item for item in (a_error, aaaa_error, https_error) if item]
    return {
        "SOURCE": "vpn_gate",
        "OBSERVED_AT": utc_now(),
        "TARGET_ID": target["id"],
        "TARGET_DOMAIN": target["domain"],
        "DNS_A_RESULT": a_result,
        "DNS_A_ADDRESSES": "|".join(a_addresses),
        "DNS_A_RU_PREFIXES": "|".join(a_ru),
        "DNS_AAAA_RESULT": aaaa_result,
        "DNS_AAAA_ADDRESSES": "|".join(aaaa_addresses),
        "DNS_AAAA_RU_PREFIXES": "|".join(aaaa_ru),
        "HTTPS_RESULT": https_result,
        "HTTP_STATUS": http_status if http_status is not None else "",
        "ERROR": " | ".join(errors)[:500],
        "EXIT_IP": exit_info["ip"],
        "EXIT_COUNTRY": exit_info["country"],
        "EXIT_ASN": exit_info["asn"],
        "EXIT_ORG": exit_info["org"],
    }


def run(args: argparse.Namespace) -> int:
    inventory_rows, networks = runner.read_inventory(pathlib.Path(args.inventory))
    targets = [target for target in runner.load_targets(pathlib.Path(args.targets))
               if "RU" in target.get("country_scope", [])]
    output = pathlib.Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    csv_text = fetch_bytes(VPN_GATE_API, timeout=40).decode("utf-8", "replace")
    servers = parse_vpngate_csv(csv_text)
    selected = servers[:args.max_servers]
    raw_rows: list[dict[str, Any]] = [{
        "source": "vpn_gate_official_api",
        "url": VPN_GATE_API,
        "retrieved_at": utc_now(),
        "ru_openvpn_servers_with_usable_profiles": len(servers),
        "selected_servers": len(selected),
        "policy": "RU country in VPN Gate record; ISP/residential status is not assumed",
    }]
    provider_rows: list[dict[str, Any]] = []
    measurement_rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    exit_categories: collections.Counter[str] = collections.Counter()
    connection_counts: collections.Counter[str] = collections.Counter()

    for server in selected:
        server_ip = server["server_ip"]
        server_category, server_prefix = runner.map_address(server_ip, networks)
        try:
            server_meta = ip_metadata(f"https://ipwho.is/{server_ip}")
        except ProbeError:
            server_meta = {"asn": 0, "org": ""}
        server_origin = network_info(server_ip)
        server_asn = server_meta["asn"] or server_origin["asn"]
        server_meta["asn"] = server_asn
        server_meta["network_prefix"] = server_origin["prefix"]
        ptr = resolve_ptr(server_ip)
        provider = {
            "SOURCE": "VPN_GATE",
            "SERVER_HOSTNAME": server["hostname"],
            "SERVER_IP": server_ip,
            "SERVER_COUNTRY": server["country_long"],
            "SERVER_ASN": server_asn,
            "SERVER_PREFIX": server_origin["prefix"],
            "SERVER_ORG": server_meta["org"],
            "SERVER_PTR": ptr,
            "SERVER_GEOIP_CATEGORY": server_category,
            "SERVER_GEOIP_RU_PREFIX": server_prefix,
            "VPN_SCORE": server["score"],
            "VPN_PING_MS": server["ping_ms"],
            "VPN_SPEED_BPS": server["speed_bps"],
            "VPN_SESSIONS": server["vpn_sessions"],
            "VPN_UPTIME": server["uptime"],
            "EXIT_IP": "",
            "EXIT_COUNTRY": "",
            "EXIT_ASN": "",
            "EXIT_PREFIX": "",
            "EXIT_ORG": "",
            "EXIT_GEOIP_CATEGORY": "",
            "EXIT_GEOIP_RU_PREFIX": "",
            "CONNECTION_RESULT": "NOT_ATTEMPTED",
            "TARGETS_TESTED": 0,
        }
        connection_counts["selected"] += 1
        with tempfile.TemporaryDirectory(prefix="geoip-vpngate-") as directory:
            tmp = pathlib.Path(directory)
            auth_path = tmp / "auth.txt"
            auth_path.write_text("vpn\nvpn\n", encoding="ascii")
            config_path = tmp / "client.ovpn"
            config_path.write_text(build_safe_openvpn_config(server, auth_path), encoding="utf-8")
            log_path = tmp / "openvpn.log"
            process = None
            try:
                with FirewallGuard(server_ip, server["profile"]["proto"], server["profile"]["port"]):
                    with ResolverGuard():
                        with log_path.open("w", encoding="utf-8") as log_stream:
                            process = subprocess.Popen(
                                ["openvpn", "--config", str(config_path), "--verb", "3"],
                                stdout=log_stream, stderr=subprocess.STDOUT,
                            )
                            try:
                                wait_for_tunnel(process, args.connect_timeout)
                                exit_info = ip_metadata()
                                if exit_info["country"] != "RU":
                                    provider["CONNECTION_RESULT"] = "REJECTED_EXIT_NOT_RU"
                                    connection_counts["rejected_non_ru_exit"] += 1
                                else:
                                    exit_origin = network_info(exit_info["ip"])
                                    exit_info["network_prefix"] = exit_origin["prefix"]
                                    exit_info["asn"] = exit_info["asn"] or exit_origin["asn"]
                                    exit_category, exit_prefix = runner.map_address(exit_info["ip"], networks)
                                    provider.update({
                                        "EXIT_IP": exit_info["ip"],
                                        "EXIT_COUNTRY": exit_info["country"],
                                        "EXIT_ASN": exit_info["asn"],
                                        "EXIT_PREFIX": exit_info["network_prefix"],
                                        "EXIT_ORG": exit_info["org"],
                                        "EXIT_GEOIP_CATEGORY": exit_category,
                                        "EXIT_GEOIP_RU_PREFIX": exit_prefix,
                                        "CONNECTION_RESULT": "CONNECTED_RU_EGRESS",
                                    })
                                    connection_counts["connected_ru_exit"] += 1
                                    exit_categories[exit_category] += 1
                                    if exit_category != "RU":
                                        candidates.append({
                                            "CANDIDATE_TYPE": "VPN_EXIT_IP",
                                            "SERVER_HOSTNAME": server["hostname"],
                                            "SERVER_IP": server_ip,
                                            "EXIT_IP": exit_info["ip"],
                                            "EXIT_COUNTRY": exit_info["country"],
                                            "EXIT_ASN": exit_info["asn"],
                                            "EXIT_ORG": exit_info["org"],
                                            "GEOIP_CATEGORY": exit_category,
                                            "MATCHED_RU_PREFIX": exit_prefix,
                                            "REASON": "IP metadata reports RU but the published GeoIP inventory does not map this exit IP to RU",
                                            "REVIEW_POLICY": "REVIEW_ONLY_NO_AUTOMATIC_CIDR_CHANGE",
                                        })
                                    for target in targets:
                                        row = test_target(target, exit_info, networks, args.request_timeout)
                                        row.update({
                                            "SERVER_HOSTNAME": server["hostname"],
                                            "SERVER_IP": server_ip,
                                            "SERVER_ASN": server_asn,
                                            "SERVER_ORG": server_meta["org"],
                                            "EXIT_GEOIP_CATEGORY": exit_category,
                                            "EXIT_GEOIP_RU_PREFIX": exit_prefix,
                                        })
                                        measurement_rows.append(row)
                                        provider["TARGETS_TESTED"] += 1
                            except (ProbeError, OSError, subprocess.SubprocessError) as exc:
                                provider["CONNECTION_RESULT"] = "CONNECT_OR_VERIFY_FAILED"
                                provider["ERROR"] = str(exc)[:400]
                                connection_counts["connect_or_verify_failed"] += 1
                            finally:
                                if process and process.poll() is None:
                                    process.terminate()
                                    try:
                                        process.wait(timeout=8)
                                    except subprocess.TimeoutExpired:
                                        process.kill()
                                        process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError, ProbeError) as exc:
                provider["CONNECTION_RESULT"] = "FIREWALL_OR_TUNNEL_SETUP_FAILED"
                provider["ERROR"] = str(exc)[:400]
                connection_counts["setup_failed"] += 1
            if provider["CONNECTION_RESULT"] not in {"CONNECTED_RU_EGRESS", "REJECTED_EXIT_NOT_RU"}:
                try:
                    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
                    if tail:
                        raw_rows.append({
                            "source": "openvpn_diagnostic_tail",
                            "server_hostname": server["hostname"],
                            "lines": tail,
                        })
                except OSError:
                    pass
        provider_rows.append(provider)

    for row in measurement_rows:
        exit_ip = row.get("EXIT_IP")
        row["EXIT_IP"] = exit_ip or ""
    candidates = candidates[:]
    runner.write_tsv(output / "vpn_gate_providers.tsv", provider_rows, PROVIDER_FIELDS)
    runner.write_jsonl(output / "vpn_gate_measurements.jsonl", measurement_rows)
    runner.write_tsv(output / "vpn_gate_geoip_candidates.tsv", candidates, CANDIDATE_FIELDS)
    runner.write_jsonl(output / "vpn_gate_raw.jsonl", raw_rows)
    summary = {
        "generated_at": utc_now(),
        "source": "VPN Gate official CSV API; vpnobratno.info is a public directory of VPN Gate Russian volunteer nodes",
        "selected_vpn_gate_ru_servers": len(selected),
        "usable_ru_openvpn_servers_discovered": len(servers),
        "connection_counts": dict(connection_counts),
        "exit_geoip_categories": dict(exit_categories),
        "targets_in_ru_scope": len(targets),
        "target_measurements": len(measurement_rows),
        "geoip_candidates": len(candidates),
        "provider_rows": len(provider_rows),
        "policy": {
            "vpn_gate_country_field_is_not_a_residential_attestation": True,
            "volunteer_access_network_class": "RESIDENTIAL_OR_OTHER_ACCESS_NETWORK_UNVERIFIED",
            "only_ru_country_exits_are_tested": True,
            "non_ru_exit_is_rejected": True,
            "non_tunnel_egress_is_firewall_blocked_while_connected": True,
            "ipv6_direct_egress_is_firewall_blocked": True,
            "http_response_including_403_or_5xx_is_transport_observation_only": True,
            "timeouts_are_not_block_verdicts": True,
            "geoip_mutation": False,
            "automatic_cidr_additions": False,
        },
        "limitations": [
            "VPN Gate nodes are volunteer-operated; a Russian exit IP does not prove a residential household line.",
            "ISP/ASN metadata is supporting attribution only; confirm operator and access type independently before using a range decision.",
            "The run tests declared RU-scope service hostnames, not every address in every GeoIP CIDR.",
            "Only IPv4 VPN tunnel egress is used; IPv6 host egress is blocked during the test and AAAA resolution is recorded without an IPv6 HTTPS tunnel test.",
            "VPN Gate may retain connection logs; only minimal public DNS/HTTPS requests are sent and no credentials or user data are submitted.",
        ],
    }
    (output / "vpn_gate_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="GeoIP RU/PRIVATE inventory TSV")
    parser.add_argument("--targets", default=".github/reachability/targets.json")
    parser.add_argument("--output-dir", default="reachability-output")
    parser.add_argument("--max-servers", type=int, default=3)
    parser.add_argument("--connect-timeout", type=int, default=60)
    parser.add_argument("--request-timeout", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.max_servers <= 6:
        parser.error("--max-servers must be between 1 and 6")
    if not 10 <= args.connect_timeout <= 180:
        parser.error("--connect-timeout must be between 10 and 180 seconds")
    if not 3 <= args.request_timeout <= 30:
        parser.error("--request-timeout must be between 3 and 30 seconds")
    missing = [name for name in ("openvpn", "ip", "iptables", "ip6tables",
                                 "iptables-save", "ip6tables-save",
                                 "iptables-restore", "ip6tables-restore") if not shutil.which(name)]
    if missing:
        parser.error("missing system commands: " + ", ".join(missing))
    if hasattr(__import__("os"), "geteuid") and __import__("os").geteuid() != 0:
        parser.error("run as root (for the fail-closed tunnel firewall and resolver isolation)")
    try:
        return run(args)
    except (OSError, ValueError, ProbeError, json.JSONDecodeError) as exc:
        print(f"VPN Gate reachability error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
