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
from html.parser import HTMLParser
import ipaddress
import io
import json
import http.client
import pathlib
import re
import shlex
import shutil
import socket
import ssl
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
VPNOBRATNO_LIST_URL = "https://vpnobratno.info/russia_server_list.html"
VPNOBRATNO_HOST = "vpnobratno.info"
VPNOBRATNO_PROFILE_RE = re.compile(
    r"^/servers/(?P<hostname>vpn[0-9]+\.opengw\.net)/"
    r"(?P=hostname)_(?P<address_mode>ddns|ip)_(?P<transport>udp|tcp)\.ovpn$",
    re.IGNORECASE,
)
VPNOBRATNO_VARIANT_ORDER = {
    "ip_udp": 0, "ddns_udp": 1, "ip_tcp": 2, "ddns_tcp": 3,
}
IP_INFO_URLS = (
    "https://ipwho.is/",
    "https://ipapi.co/json/",
    "https://ipinfo.io/json",
)
RIPESTAT_NETWORK_INFO = "https://stat.ripe.net/data/network-info/data.json"
USER_AGENT = "Geoip-ru-server-vpn-gate-validation/1.0"
PROVIDER_FIELDS = [
    "SOURCE", "PROFILE_VARIANT", "PROFILE_URL", "SERVER_HOSTNAME", "SERVER_IP", "SERVER_COUNTRY",
    "SERVER_ASN", "SERVER_ASN_IP_METADATA", "SERVER_ASN_RIPESTAT", "SERVER_ASN_CONFLICT",
    "SERVER_PREFIX", "SERVER_ORG", "SERVER_PTR",
    "SERVER_GEOIP_CATEGORY", "SERVER_GEOIP_RU_PREFIX",
    "VPN_SCORE", "VPN_PING_MS", "VPN_SPEED_BPS", "VPN_SESSIONS",
    "VPN_UPTIME", "ERROR", "EXIT_IP", "EXIT_COUNTRY", "EXIT_ASN",
    "EXIT_ASN_IP_METADATA", "EXIT_ASN_RIPESTAT", "EXIT_ASN_CONFLICT",
    "EXIT_PREFIX", "EXIT_ORG", "EXIT_GEOIP_CATEGORY",
    "EXIT_GEOIP_RU_PREFIX", "CONNECTION_RESULT", "TARGETS_TESTED",
]
MEASUREMENT_FIELDS = [
    "SOURCE", "OBSERVED_AT", "PROFILE_VARIANT", "PROFILE_URL", "SERVER_HOSTNAME", "SERVER_IP",
    "SERVER_ASN", "SERVER_ASN_IP_METADATA", "SERVER_ASN_RIPESTAT", "SERVER_ASN_CONFLICT",
    "SERVER_ORG", "EXIT_IP", "EXIT_COUNTRY",
    "EXIT_ASN", "EXIT_ASN_IP_METADATA", "EXIT_ASN_RIPESTAT", "EXIT_ASN_CONFLICT",
    "EXIT_ORG", "EXIT_GEOIP_CATEGORY", "EXIT_GEOIP_RU_PREFIX",
    "TARGET_ID", "TARGET_DOMAIN", "DNS_A_RESULT", "DNS_A_ADDRESSES",
    "DNS_A_RU_PREFIXES", "DNS_AAAA_RESULT", "DNS_AAAA_ADDRESSES",
    "DNS_AAAA_RU_PREFIXES", "HTTPS_RESULT", "HTTP_STATUS", "ERROR",
]
CANDIDATE_FIELDS = [
    "CANDIDATE_TYPE", "SERVER_HOSTNAME", "SERVER_IP", "EXIT_IP",
    "EXIT_COUNTRY", "EXIT_ASN", "EXIT_ASN_IP_METADATA", "EXIT_ASN_RIPESTAT",
    "EXIT_ASN_CONFLICT", "EXIT_ORG", "GEOIP_CATEGORY",
    "MATCHED_RU_PREFIX", "REASON", "REVIEW_POLICY",
]


class ProbeError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


DOH_RESOLVERS = (
    ("cloudflare-dns.com", "1.1.1.1", "cloudflare"),
    ("dns.google", "8.8.8.8", "google"),
)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to an IP while retaining hostname SNI/cert checks."""
    def __init__(self, host: str, address: str, port: int = 443, timeout: int = 15):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self.pinned_address = address

    def connect(self):
        sock = self._create_connection(
            (self.pinned_address, self.port), self.timeout, self.source_address
        )
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def doh_query(domain: str, record_type: str, timeout: int = 10) -> list[str]:
    """Resolve one RR type over HTTPS to a pinned public DoH resolver, without system DNS."""
    qtype = record_type.upper()
    if qtype not in {"A", "AAAA"}:
        raise ValueError("DoH record type must be A or AAAA")
    errors: list[str] = []
    for host, address, provider in DOH_RESOLVERS:
        connection = None
        try:
            connection = PinnedHTTPSConnection(host, address, timeout=timeout)
            if provider == "cloudflare":
                path = "/dns-query?" + urllib.parse.urlencode({"name": domain, "type": qtype})
                headers = {"Accept": "application/dns-json", "User-Agent": USER_AGENT}
            else:
                path = "/resolve?" + urllib.parse.urlencode({"name": domain, "type": qtype})
                headers = {"Accept": "application/dns-json", "User-Agent": USER_AGENT}
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            payload = response.read(1_000_000)
            if response.status != 200:
                raise ProbeError(f"{provider} DoH returned HTTP {response.status}")
            result = json.loads(payload.decode("utf-8"))
            if parse_int(result.get("Status"), -1) != 0:
                raise ProbeError(f"{provider} DoH DNS status {result.get('Status')}")
            expected_version = 4 if qtype == "A" else 6
            values = []
            for answer in result.get("Answer") or []:
                if parse_int(answer.get("type")) != (1 if qtype == "A" else 28):
                    continue
                value = str(answer.get("data") or "").strip()
                try:
                    parsed = ipaddress.ip_address(value)
                except ValueError:
                    continue
                if parsed.version == expected_version and parsed.is_global:
                    values.append(str(parsed))
            if values:
                return sorted(set(values))
            return []
        except (OSError, http.client.HTTPException, ssl.SSLError, ValueError, ProbeError) as exc:
            errors.append(f"{provider}: {exc}")
        finally:
            if connection is not None:
                connection.close()
    raise ProbeError("all pinned DNS-over-HTTPS resolvers failed: " + "; ".join(errors))


def fetch_https_pinned(url: str, timeout: int) -> bytes:
    """Retry an HTTPS API request with a DoH-resolved IP and certificate-checked SNI."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ProbeError("pinned fallback supports HTTPS URLs only")
    host = parts.hostname
    # This backend deliberately uses an IPv4-only VPN tunnel. Do not attempt
    # an AAAA-only connection: host IPv6 egress is blocked by the kill-switch.
    addresses = doh_query(host, "A", timeout=min(timeout, 12))
    if not addresses:
        raise ProbeError(
            f"DoH returned no global IPv4 address for {host}; "
            "IPv6 HTTPS is not enabled by this IPv4-tunnel workflow"
        )
    path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
    errors: list[str] = []
    for address in addresses[:3]:
        connection = None
        try:
            connection = PinnedHTTPSConnection(
                host, address, port=parts.port or 443, timeout=timeout
            )
            connection.request(
                "GET", path,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "close"},
            )
            response = connection.getresponse()
            payload = response.read(8_000_000)
            if response.status < 200 or response.status >= 300:
                raise ProbeError(f"HTTP {response.status} from {host}")
            return payload
        except (OSError, http.client.HTTPException, ssl.SSLError, ProbeError) as exc:
            errors.append(f"{address}: {exc}")
        finally:
            if connection is not None:
                connection.close()
    raise ProbeError(f"pinned HTTPS request failed for {host}: " + "; ".join(errors))


def fetch_bytes(url: str, timeout: int = 25) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.read(8_000_000)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # A resolver/NSS failure must not prevent metadata verification after
        # the VPN route is established. The fallback queries DoH via a pinned
        # resolver IP, then pins the API's address while preserving TLS SNI.
        try:
            return fetch_https_pinned(url, timeout)
        except ProbeError as fallback_error:
            raise ProbeError(
                f"request failed for {urllib.parse.urlparse(url).netloc}: {exc}; "
                f"pinned DoH fallback: {fallback_error}"
            ) from fallback_error


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
        match = re.fullmatch(r"<(ca|tls-auth|tls-crypt|tls-crypt-v2)>", line, re.IGNORECASE)
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
    remote_host = remotes[0][1].strip().rstrip(".").lower()
    if not re.fullmatch(r"(?:[a-z0-9-]+\.)*[a-z0-9-]+|(?:[0-9]{1,3}\.){3}[0-9]{1,3}", remote_host):
        raise ValueError("OpenVPN remote host is not a supported hostname or IPv4 literal")
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

    for directive_name in ("tls-auth", "tls-crypt", "tls-crypt-v2"):
        for item in directives:
            if item[0].lower() == directive_name and directive_name not in blocks:
                if len(item) < 2 or item[1].lower() != "[inline]":
                    raise ValueError(
                        f"OpenVPN {directive_name} references an external key file; unsafe to execute"
                    )

    def selected_value(name: str, pattern: str, maximum_tokens: int = 2) -> str:
        values = [
            item[1] for item in directives
            if item[0].lower() == name and len(item) == maximum_tokens
        ]
        if not values:
            return ""
        value = values[0]
        if not re.fullmatch(pattern, value):
            return ""
        return value

    def selected_x509_name() -> tuple[str, str]:
        for item in directives:
            if item[0].lower() != "verify-x509-name" or len(item) not in {2, 3}:
                continue
            name = item[1]
            mode = item[2].lower() if len(item) == 3 else ""
            if (
                re.fullmatch(r"[A-Za-z0-9_.:,=/+ -]{1,200}", name)
                and mode in {"", "name", "subject"}
            ):
                return name, mode
        return "", ""

    remote_cert_ku = []
    for item in directives:
        if item[0].lower() == "remote-cert-ku" and 2 <= len(item) <= 5:
            values = item[1:]
            if all(re.fullmatch(r"0x[0-9A-Fa-f]{1,8}", value) for value in values):
                remote_cert_ku = values
                break

    key_direction = selected_value("key-direction", r"[01]")
    tls_version_min = selected_value("tls-version-min", r"(?:1\.[0-3]|or-highest|default)")
    tls_version_max = selected_value("tls-version-max", r"(?:1\.[0-3]|or-highest|default)")
    tls_cipher = selected_value("tls-cipher", r"[-A-Za-z0-9_:.!@,+=/]{1,256}")
    tls_ciphersuites = selected_value("tls-ciphersuites", r"[-A-Za-z0-9_:.!@,+=/]{1,256}")
    tls_cert_profile = selected_value("tls-cert-profile", r"(?:legacy|preferred)")
    remote_cert_eku = selected_value("remote-cert-eku", r"[A-Za-z0-9_.: -]{1,120}")
    verify_x509_name, verify_x509_name_mode = selected_x509_name()
    return {
        "remote_host": remote_host,
        "port": port,
        "proto": proto,
        "cipher": selected_value("cipher", r"[A-Za-z0-9_.:+-]{1,80}"),
        "auth": selected_value("auth", r"[A-Za-z0-9_.:+-]{1,80}"),
        "key_direction": key_direction,
        "tls_version_min": tls_version_min,
        "tls_version_max": tls_version_max,
        "tls_cipher": tls_cipher,
        "tls_ciphersuites": tls_ciphersuites,
        "tls_cert_profile": tls_cert_profile,
        "remote_cert_eku": remote_cert_eku,
        "remote_cert_ku": remote_cert_ku,
        "verify_x509_name": verify_x509_name,
        "verify_x509_name_mode": verify_x509_name_mode,
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
        "verb 4",
        "mute 10",
        "data-ciphers AES-256-GCM:AES-128-GCM:AES-128-CBC",
    ]
    if profile["cipher"]:
        lines.extend([f"cipher {profile['cipher']}", f"data-ciphers-fallback {profile['cipher']}"])
    if profile["auth"]:
        lines.append(f"auth {profile['auth']}")
    for option in ("tls_version_min", "tls_version_max", "tls_cipher", "tls_ciphersuites", "tls_cert_profile", "remote_cert_eku"):
        if profile.get(option):
            directive = {
                "tls_version_min": "tls-version-min",
                "tls_version_max": "tls-version-max",
                "tls_cipher": "tls-cipher",
                "tls_ciphersuites": "tls-ciphersuites",
                "tls_cert_profile": "tls-cert-profile",
                "remote_cert_eku": "remote-cert-eku",
            }[option]
            value = f'"{profile[option]}"' if option == "remote_cert_eku" else profile[option]
            lines.append(f"{directive} {value}")
    if profile.get("remote_cert_ku"):
        lines.append("remote-cert-ku " + " ".join(profile["remote_cert_ku"]))
    if profile.get("verify_x509_name"):
        x509_line = 'verify-x509-name "' + profile["verify_x509_name"] + '"'
        if profile.get("verify_x509_name_mode"):
            x509_line += " " + profile["verify_x509_name_mode"]
        lines.append(x509_line)
    if profile["key_direction"] and "tls-auth" in profile["blocks"]:
        lines.append(f"key-direction {profile['key_direction']}")
    for name in ("ca", "tls-auth", "tls-crypt", "tls-crypt-v2"):
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
        prefix = str(data.get("prefix") or "").strip()
        try:
            network = ipaddress.ip_network(prefix, strict=False)
            if ipaddress.ip_address(address) not in network:
                prefix = ""
        except ValueError:
            prefix = ""
        return {"prefix": prefix, "asn": asn}
    except ProbeError:
        return {"prefix": "", "asn": 0}


def _parse_ip_metadata(endpoint: str) -> dict[str, Any]:
    payload = fetch_json(endpoint, timeout=15)
    connection = payload.get("connection") or {}
    address = str(payload.get("ip") or "").strip()
    parsed = ipaddress.ip_address(address)
    if not parsed.is_global:
        raise ProbeError("reported IP address is not globally routable")
    country = str(payload.get("country_code") or payload.get("country") or "").upper()
    if not re.fullmatch(r"[A-Z]{2}", country):
        raise ProbeError("IP metadata response has no valid country code")
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



class VPNObratnoLinkParser(HTMLParser):
    """Collect links only; profile URLs are validated separately before download."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = next((value for key, value in attrs if key.lower() == "href"), None)
        if href:
            self.hrefs.append(href)


def parse_vpnobratno_listing(html: str) -> list[dict[str, str]]:
    """Return supported same-origin OpenVPN profile links from the public RU list."""
    parser = VPNObratnoLinkParser()
    parser.feed(html)
    profiles: dict[str, dict[str, str]] = {}
    for href in parser.hrefs:
        absolute = urllib.parse.urljoin(VPNOBRATNO_LIST_URL, href)
        parts = urllib.parse.urlsplit(absolute)
        if (
            parts.scheme.lower() != "https"
            or (parts.hostname or "").lower() != VPNOBRATNO_HOST
            or parts.port not in (None, 443)
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
        ):
            continue
        match = VPNOBRATNO_PROFILE_RE.fullmatch(parts.path)
        if not match:
            continue
        hostname = match.group("hostname").lower()
        address_mode = match.group("address_mode").lower()
        transport = match.group("transport").lower()
        variant = f"{address_mode}_{transport}"
        profile_url = urllib.parse.urlunsplit(
            ("https", VPNOBRATNO_HOST, parts.path, "", "")
        )
        profiles.setdefault(profile_url, {
            "hostname": hostname,
            "address_mode": address_mode,
            "transport": transport,
            "profile_variant": variant,
            "profile_url": profile_url,
        })
    # Keep the site's server ordering but put the most robust-to-DNS UDP profile
    # first within each server, then the remaining UDP and TCP variants.
    by_host: dict[str, list[dict[str, str]]] = {}
    host_order: list[str] = []
    for profile in profiles.values():
        hostname = profile["hostname"]
        if hostname not in by_host:
            host_order.append(hostname)
            by_host[hostname] = []
        by_host[hostname].append(profile)
    ordered: list[dict[str, str]] = []
    for hostname in host_order:
        ordered.extend(sorted(
            by_host[hostname],
            key=lambda item: VPNOBRATNO_VARIANT_ORDER[item["profile_variant"]],
        ))
    return ordered


def _public_ipv4_answers(hostname: str, resolver: Any = socket.getaddrinfo) -> list[str]:
    try:
        records = resolver(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"could not resolve VPNObratno server hostname {hostname}: {exc}") from exc
    answers: list[str] = []
    for record in records:
        try:
            address = ipaddress.ip_address(record[4][0])
        except (IndexError, TypeError, ValueError):
            continue
        if address.version == 4 and address.is_global:
            answers.append(str(address))
    return sorted(set(answers))


def resolve_vpnobratno_server_ip(
    expected_hostname: str,
    remote_host: str,
    address_mode: str,
    resolver: Any = socket.getaddrinfo,
) -> str:
    """Pin a profile to a public IPv4 that belongs to its listed VPN Gate hostname."""
    expected = expected_hostname.rstrip(".").lower()
    if not re.fullmatch(r"vpn[0-9]+\.opengw\.net", expected):
        raise ValueError("VPNObratno listing has an unsupported server hostname")
    if address_mode == "ddns":
        if remote_host.rstrip(".").lower() != expected:
            raise ValueError("DDNS profile remote does not match its listing hostname")
        answers = _public_ipv4_answers(expected, resolver)
        if not answers:
            raise ValueError("VPNObratno DDNS hostname has no global IPv4 answer")
        return answers[0]
    if address_mode == "ip":
        try:
            address = ipaddress.ip_address(remote_host)
        except ValueError as exc:
            raise ValueError("IP profile remote is not an IP literal") from exc
        if address.version != 4 or not address.is_global:
            raise ValueError("IP profile remote is not a global IPv4 address")
        answers = _public_ipv4_answers(expected, resolver)
        if str(address) not in answers:
            raise ValueError("IP profile address does not match the listed hostname DNS")
        return str(address)
    raise ValueError("unsupported VPNObratno address mode")


def discover_vpnobratno_servers(
    fetcher: Any = fetch_bytes,
    resolver: Any = socket.getaddrinfo,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Download and validate listed profiles without executing supplied directives."""
    page = fetcher(VPNOBRATNO_LIST_URL, timeout=40).decode("utf-8", "replace")
    listed = parse_vpnobratno_listing(page)
    if not listed:
        raise ProbeError("VPNObratno page contains no supported OpenVPN profile links")
    servers: list[dict[str, Any]] = []
    skipped = collections.Counter()
    for entry in listed:
        try:
            payload = fetcher(entry["profile_url"], timeout=25)
            if not payload or len(payload) > 64_000:
                raise ValueError("profile is empty or exceeds 64 KiB")
            config = payload.decode("utf-8")
            profile = inspect_openvpn_profile(config)
            expected_proto = "udp" if entry["transport"] == "udp" else "tcp-client"
            if profile["proto"] != expected_proto:
                raise ValueError("profile transport does not match the listed variant")
            server_ip = resolve_vpnobratno_server_ip(
                entry["hostname"], profile["remote_host"], entry["address_mode"], resolver
            )
            servers.append({
                "hostname": entry["hostname"],
                "server_ip": server_ip,
                "country_long": "Russian Federation (VPNObratno listing)",
                "country_short": "RU",
                "score": 0,
                "ping_ms": 0,
                "speed_bps": 0,
                "vpn_sessions": 0,
                "uptime": "",
                "config": config,
                "profile": profile,
                "source": "VPNOBRATNO",
                "profile_variant": entry["profile_variant"].upper(),
                "profile_url": entry["profile_url"],
            })
        except (OSError, ProbeError, UnicodeDecodeError, ValueError) as exc:
            skipped[type(exc).__name__ + ": " + str(exc)[:120]] += 1
    if not servers:
        raise ProbeError(
            "VPNObratno listed profiles were found, but none passed validation; "
            + json.dumps(dict(skipped), ensure_ascii=False, sort_keys=True)
        )
    meta = {
        "listing_url": VPNOBRATNO_LIST_URL,
        "profile_links_found": len(listed),
        "usable_profiles": len(servers),
        "unique_server_hostnames": len({server["hostname"] for server in servers}),
        "profile_variants": dict(collections.Counter(
            server["profile_variant"] for server in servers
        )),
        "skipped_profiles": dict(skipped),
        "profile_order": ["IP_UDP", "DDNS_UDP", "IP_TCP", "DDNS_TCP"],
        "profile_directives_executed": False,
    }
    return servers, meta


def select_diverse_servers(
    servers: list[dict[str, Any]],
    max_servers: int,
    candidate_limit: int = 24,
    max_attempts: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Order a bounded fallback list: one candidate per origin ASN before repeats.

    max_servers is the number of successful RU exits requested. max_attempts
    controls how many candidates may be tried to reach that count.
    """
    if max_servers < 1:
        raise ValueError("max_servers must be positive")
    attempt_limit = max_servers if max_attempts is None else max_attempts
    if attempt_limit < max_servers:
        raise ValueError("max_attempts must be >= max_servers")
    if attempt_limit > 6:
        raise ValueError("max_attempts must be <= 6")
    candidates = servers[:min(len(servers), max(candidate_limit, attempt_limit, max_servers))]
    groups: dict[str, list[dict[str, Any]]] = {}
    asn_lookups = 0
    origin_cache: dict[str, dict[str, Any]] = {}
    for server in candidates:
        server_ip = server["server_ip"]
        if server_ip not in origin_cache:
            origin_cache[server_ip] = network_info(server_ip)
        origin = dict(origin_cache[server_ip])
        asn = parse_int(origin.get("asn"))
        server["_network_info"] = origin
        server["_selection_asn"] = asn
        group = f"AS{asn}" if asn > 0 else "ASN_UNVERIFIED"
        groups.setdefault(group, []).append(server)
        asn_lookups += 1

    group_order = sorted(
        groups,
        key=lambda group: (
            group == "ASN_UNVERIFIED",
            -groups[group][0]["score"],
            groups[group][0]["hostname"],
        ),
    )
    ordered: list[dict[str, Any]] = []
    # First pass: one best-scoring candidate per observed ASN.
    for group in group_order:
        ordered.append(groups[group][0])
    # Subsequent passes: one fallback per ASN per round, rather than exhausting
    # all servers from the highest-ranked provider first.
    for index in range(1, max((len(value) for value in groups.values()), default=0)):
        for group in group_order:
            if index < len(groups[group]):
                ordered.append(groups[group][index])
    selected = ordered[:attempt_limit]
    selected_asns = sorted({
        server["_selection_asn"] for server in selected
        if server["_selection_asn"] > 0
    })
    return selected, {
        "candidate_servers_inspected": len(candidates),
        "server_asn_lookups": asn_lookups,
        "distinct_candidate_asns": len([group for group in groups if group != "ASN_UNVERIFIED"]),
        "attempt_candidates_selected": len(selected),
        "max_connection_attempts": attempt_limit,
        "selected_distinct_asns": len(selected_asns),
        "selected_asns": selected_asns,
        "unverified_asn_candidates": len(groups.get("ASN_UNVERIFIED", [])),
        "selection_policy": "one_best_candidate_per_observed_asn_before_second_server_from_same_asn",
    }


def ip_metadata(url: str | None = None) -> dict[str, Any]:
    """Get metadata for a known server IP or require two-source egress consensus."""
    endpoints = (url,) if url else IP_INFO_URLS
    observations: list[dict[str, Any]] = []
    errors: list[str] = []
    for endpoint in endpoints:
        try:
            observation = _parse_ip_metadata(endpoint)
            if url:
                return observation
            observations.append(observation)
        except (ProbeError, ValueError, urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{urllib.parse.urlparse(endpoint).netloc}: {exc}")
        if len(observations) >= 2:
            break

    if url:
        raise ProbeError("unable to identify VPN server IP metadata: " + "; ".join(errors[:2]))
    if len(observations) < 2:
        raise ProbeError(
            "VPN exit verification requires two independent IP metadata services; "
            + "; ".join(errors[:2])
        )
    first = observations[0]
    if any(item["ip"] != first["ip"] or item["country"] != first["country"] for item in observations[1:]):
        raise ProbeError("independent IP metadata services disagree on exit IP or country")
    merged = dict(first)
    merged["asn"] = next((item["asn"] for item in observations if item["asn"]), 0)
    merged["org"] = next((item["org"] for item in observations if item["org"]), "")
    merged["source"] = "|".join(item["source"] for item in observations)
    merged["verified_by_sources"] = len(observations)
    return merged


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
        if restore_errors:
            raise ProbeError("failed to restore host firewall: " + "; ".join(restore_errors))


class ResolverGuard:
    """Compatibility scope that deliberately never edits the host resolver config.

    System NSS lookups are attempted while the fail-closed firewall is active.
    If the runner's configured resolver is unavailable through the tunnel,
    fetch_bytes/resolve_domain_families use IP-pinned DNS-over-HTTPS instead.
    """
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def wait_for_tunnel(
    process: subprocess.Popen,
    timeout: int,
    log_path: pathlib.Path | None = None,
) -> str:
    """Wait for a tunnel, but stop early on explicit TLS/authentication failures."""
    deadline = time.monotonic() + timeout
    fatal_markers = (
        "TLS key negotiation failed to occur",
        "TLS handshake failed",
        "TLS Error:",
        "VERIFY ERROR:",
        "AUTH_FAILED",
        "Exiting due to fatal error",
    )
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ProbeError(f"OpenVPN exited early with code {process.returncode}")
        if log_path and log_path.exists():
            try:
                tail = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-30:])
            except OSError:
                tail = ""
            for marker in fatal_markers:
                if marker in tail:
                    raise ProbeError(f"OpenVPN reported {marker}")
        result = run_command(["ip", "-4", "route", "get", "1.1.1.1"], check=False)
        if result.returncode == 0:
            match = re.search(r"\bdev\s+(tun\S*)", result.stdout)
            if match:
                return match.group(1)
        time.sleep(1)
    raise ProbeError(f"OpenVPN tunnel did not install an IPv4 default route within {timeout}s")


def resolve_domain_families(
    domain: str, timeout: int
) -> tuple[tuple[str, list[str], str], tuple[str, list[str], str]]:
    """Resolve A and AAAA through the tunnel; use pinned DoH if system NSS fails."""
    system_error = ""
    try:
        socket.setdefaulttimeout(timeout)
        infos = socket.getaddrinfo(domain, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ipv4 = sorted({item[4][0] for item in infos if item[0] == socket.AF_INET})
        ipv6 = sorted({item[4][0] for item in infos if item[0] == socket.AF_INET6})
        return (
            ("DNS_ANSWER" if ipv4 else "DNS_NO_ANSWER", ipv4, ""),
            ("DNS_ANSWER" if ipv6 else "DNS_NO_ANSWER", ipv6, ""),
        )
    except (socket.gaierror, OSError) as exc:
        system_error = str(exc)[:200]

    try:
        ipv4 = doh_query(domain, "A", timeout)
        ipv6 = doh_query(domain, "AAAA", timeout)
        return (
            ("DNS_ANSWER" if ipv4 else "DNS_NO_ANSWER", ipv4, ""),
            ("DNS_ANSWER" if ipv6 else "DNS_NO_ANSWER", ipv6, ""),
        )
    except ProbeError as exc:
        error = f"system resolver: {system_error}; pinned DoH: {str(exc)[:200]}"[:400]
        return ("DNS_ERROR", [], error), ("DNS_ERROR", [], error)


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
        # A system resolver/NSS error is not a service failure. Retry with a
        # pinned DoH-resolved IP, preserving Host, SNI and certificate checks.
        try:
            # Only IPv4 HTTPS is in scope. AAAA answers are still recorded
            # by resolve_domain_families, but IPv6 transport is firewall-blocked.
            addresses = doh_query(domain, "A", timeout=min(timeout, 12))
            if not addresses:
                return "INCONCLUSIVE", None, (
                    f"system HTTPS: {str(exc)[:160]}; pinned DoH: no global IPv4 "
                    "address (IPv6 HTTPS is not enabled)"
                )
            errors = []
            for address in addresses[:3]:
                connection = None
                try:
                    connection = PinnedHTTPSConnection(
                        domain, address, port=port, timeout=timeout
                    )
                    connection.request(
                        "HEAD", path,
                        headers={
                            "User-Agent": USER_AGENT,
                            "Accept": "*/*",
                            "Connection": "close",
                        },
                    )
                    response = connection.getresponse()
                    response.read(64_000)
                    return "HTTP_RESPONSE", int(response.status), ""
                except (OSError, http.client.HTTPException, ssl.SSLError) as fallback_exc:
                    errors.append(f"{address}: {fallback_exc}")
                finally:
                    if connection is not None:
                        connection.close()
            detail = "; ".join(errors) if errors else "DoH returned no global address"
            return "INCONCLUSIVE", None, f"system HTTPS: {str(exc)[:160]}; pinned HTTPS: {detail[:160]}"
        except ProbeError as fallback_exc:
            return "INCONCLUSIVE", None, (
                f"system HTTPS: {str(exc)[:160]}; pinned DoH: {str(fallback_exc)[:160]}"
            )


def test_target(target: dict[str, Any], exit_info: dict[str, Any], networks: dict[str, Any], timeout: int) -> dict[str, Any]:
    (a_result, a_addresses, a_error), (aaaa_result, aaaa_addresses, aaaa_error) = resolve_domain_families(
        target["domain"], timeout
    )
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


def measurement_exit_code(successful_ru_exits: int, requested_ru_exits: int) -> int:
    """A diagnostic artifact without the requested verified RU exits is not a pass."""
    return 0 if successful_ru_exits >= requested_ru_exits else 2


def run(args: argparse.Namespace) -> int:
    inventory_rows, networks = runner.read_inventory(pathlib.Path(args.inventory))
    targets = [target for target in runner.load_targets(pathlib.Path(args.targets))
               if "RU" in target.get("country_scope", [])]
    output = pathlib.Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    if args.source == "vpnobratno":
        servers, discovery_meta = discover_vpnobratno_servers()
        discovery_source = "vpnobratno.info Russian server list and linked OpenVPN profiles"
        raw_rows: list[dict[str, Any]] = [{
            "source": "vpnobratno_profile_discovery",
            "url": VPNOBRATNO_LIST_URL,
            "retrieved_at": utc_now(),
            "discovery": discovery_meta,
            "policy": "The site lists Russian VPN Gate user-operated nodes; country and access-network type are reverified from the actual tunnel exit.",
        }]
    else:
        csv_text = fetch_bytes(VPN_GATE_API, timeout=40).decode("utf-8", "replace")
        servers = parse_vpngate_csv(csv_text)
        discovery_meta = {"usable_profiles": len(servers), "source": VPN_GATE_API}
        discovery_source = "VPN Gate official CSV API"
        raw_rows = [{
            "source": "vpn_gate_official_api",
            "url": VPN_GATE_API,
            "retrieved_at": utc_now(),
            "ru_openvpn_servers_with_usable_profiles": len(servers),
            "policy": "RU country in VPN Gate record; ISP/residential status is not assumed",
        }]
    selected, selection_meta = select_diverse_servers(
        servers, args.max_servers, max_attempts=args.max_attempts
    )
    raw_rows[0]["selected_servers"] = len(selected)
    raw_rows[0]["provider_diversity_selection"] = selection_meta
    provider_rows: list[dict[str, Any]] = []
    measurement_rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    exit_categories: collections.Counter[str] = collections.Counter()
    connection_counts: collections.Counter[str] = collections.Counter()

    for server in selected:
        if connection_counts["connected_ru_exit"] >= args.max_servers:
            break
        server_ip = server["server_ip"]
        server_category, server_prefix = runner.map_address(server_ip, networks)
        try:
            server_meta = ip_metadata(f"https://ipwho.is/{server_ip}")
        except ProbeError:
            server_meta = {"asn": 0, "org": ""}
        server_origin = server.pop("_network_info", None) or network_info(server_ip)
        server_asn_ip_meta = parse_int(server_meta.get("asn"))
        server_asn_ripestat = parse_int(server_origin.get("asn"))
        server_asn_conflict = bool(
            server_asn_ip_meta and server_asn_ripestat
            and server_asn_ip_meta != server_asn_ripestat
        )
        server_asn = server_asn_ripestat or server_asn_ip_meta
        server_meta["asn"] = server_asn

        server_meta["network_prefix"] = server_origin["prefix"]
        ptr = resolve_ptr(server_ip)
        provider = {
            "SOURCE": server.get("source", "VPN_GATE"),
            "PROFILE_VARIANT": server.get("profile_variant", "VPN_GATE_API"),
            "PROFILE_URL": server.get("profile_url", ""),
            "SERVER_HOSTNAME": server["hostname"],
            "SERVER_IP": server_ip,
            "SERVER_COUNTRY": server["country_long"],
            "SERVER_ASN": server_asn,
            "SERVER_ASN_IP_METADATA": server_asn_ip_meta,
            "SERVER_ASN_RIPESTAT": server_asn_ripestat,
            "SERVER_ASN_CONFLICT": server_asn_conflict,
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
            "EXIT_ASN_IP_METADATA": "",
            "EXIT_ASN_RIPESTAT": "",
            "EXIT_ASN_CONFLICT": "",
            "EXIT_PREFIX": "",
            "EXIT_ORG": "",
            "EXIT_GEOIP_CATEGORY": "",
            "EXIT_GEOIP_RU_PREFIX": "",
            "CONNECTION_RESULT": "NOT_ATTEMPTED",
            "TARGETS_TESTED": 0,
        }
        raw_rows.append({
            "source": "openvpn_profile_safe_features",
            "server_hostname": server["hostname"],
            "discovery_source": server.get("source", "VPN_GATE"),
            "profile_variant": server.get("profile_variant", "VPN_GATE_API"),
            "profile_url": server.get("profile_url", ""),
            "profile_features": {
                "has_inline_ca": "ca" in server["profile"]["blocks"],
                "has_tls_auth": "tls-auth" in server["profile"]["blocks"],
                "has_tls_crypt": "tls-crypt" in server["profile"]["blocks"],
                "has_tls_crypt_v2": "tls-crypt-v2" in server["profile"]["blocks"],
                "tls_version_min": server["profile"].get("tls_version_min", ""),
                "tls_version_max": server["profile"].get("tls_version_max", ""),
                "tls_cipher": server["profile"].get("tls_cipher", ""),
                "tls_ciphersuites": server["profile"].get("tls_ciphersuites", ""),
                "tls_cert_profile": server["profile"].get("tls_cert_profile", ""),
                "verify_x509_name_present": bool(server["profile"].get("verify_x509_name")),
                "remote_cert_eku_present": bool(server["profile"].get("remote_cert_eku")),
                "remote_cert_ku_count": len(server["profile"].get("remote_cert_ku", [])),
            },
        })
        connection_counts["selected"] += 1
        with tempfile.TemporaryDirectory(prefix="geoip-vpngate-") as directory:
            tmp = pathlib.Path(directory)
            auth_path = tmp / "auth.txt"
            auth_path.write_text("vpn\nvpn\n", encoding="ascii")
            auth_path.chmod(0o600)
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
                                wait_for_tunnel(process, args.connect_timeout, log_path)
                                exit_info = ip_metadata()
                                if exit_info["country"] != "RU":
                                    provider["CONNECTION_RESULT"] = "REJECTED_EXIT_NOT_RU"
                                    connection_counts["rejected_non_ru_exit"] += 1
                                else:
                                    exit_origin = network_info(exit_info["ip"])
                                    exit_info["network_prefix"] = exit_origin["prefix"]
                                    exit_asn_ip_meta = parse_int(exit_info.get("asn"))
                                    exit_asn_ripestat = parse_int(exit_origin.get("asn"))
                                    exit_asn_conflict = bool(
                                        exit_asn_ip_meta and exit_asn_ripestat
                                        and exit_asn_ip_meta != exit_asn_ripestat
                                    )
                                    exit_info["asn_ip_metadata"] = exit_asn_ip_meta
                                    exit_info["asn_ripestat"] = exit_asn_ripestat
                                    exit_info["asn_conflict"] = exit_asn_conflict
                                    exit_info["asn"] = exit_asn_ripestat or exit_asn_ip_meta
                                    exit_category, exit_prefix = runner.map_address(exit_info["ip"], networks)
                                    if exit_asn_conflict:
                                        candidates.append({
                                            "CANDIDATE_TYPE": "ASN_CONFLICT",
                                            "SERVER_HOSTNAME": server["hostname"],
                                            "SERVER_IP": server_ip,
                                            "EXIT_IP": exit_info["ip"],
                                            "EXIT_COUNTRY": exit_info["country"],
                                            "EXIT_ASN": exit_info["asn"],
                                            "EXIT_ASN_IP_METADATA": exit_asn_ip_meta,
                                            "EXIT_ASN_RIPESTAT": exit_asn_ripestat,
                                            "EXIT_ASN_CONFLICT": True,
                                            "EXIT_ORG": exit_info["org"],
                                            "GEOIP_CATEGORY": exit_category,
                                            "MATCHED_RU_PREFIX": exit_prefix,
                                            "REASON": "IP metadata and RIPEstat report different origin ASNs for the VPN exit IP",
                                            "REVIEW_POLICY": "REVIEW_ONLY_ORIGIN_CONFLICT_REQUIRES_ROUTE_REVIEW",
                                        })
                                    provider.update({
                                        "EXIT_IP": exit_info["ip"],
                                        "EXIT_COUNTRY": exit_info["country"],
                                        "EXIT_ASN": exit_info["asn"],
                                        "EXIT_ASN_IP_METADATA": exit_asn_ip_meta,
                                        "EXIT_ASN_RIPESTAT": exit_asn_ripestat,
                                        "EXIT_ASN_CONFLICT": exit_asn_conflict,
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
                                            "EXIT_ASN_IP_METADATA": exit_asn_ip_meta,
                                            "EXIT_ASN_RIPESTAT": exit_asn_ripestat,
                                            "EXIT_ASN_CONFLICT": exit_asn_conflict,
                                            "EXIT_ORG": exit_info["org"],
                                            "GEOIP_CATEGORY": exit_category,
                                            "MATCHED_RU_PREFIX": exit_prefix,
                                            "REASON": "IP metadata reports RU but the published GeoIP inventory does not map this exit IP to RU",
                                            "REVIEW_POLICY": "REVIEW_ONLY_NO_AUTOMATIC_CIDR_CHANGE",
                                        })
                                    for target in targets:
                                        row = test_target(target, exit_info, networks, args.request_timeout)
                                        row.update({
                                            "SOURCE": server.get("source", "VPN_GATE"),
                                            "PROFILE_VARIANT": server.get("profile_variant", "VPN_GATE_API"),
                                            "PROFILE_URL": server.get("profile_url", ""),
                                            "SERVER_HOSTNAME": server["hostname"],
                                            "SERVER_IP": server_ip,
                                            "SERVER_ASN": server_asn,
                                            "SERVER_ASN_IP_METADATA": server_asn_ip_meta,
                                            "SERVER_ASN_RIPESTAT": server_asn_ripestat,
                                            "SERVER_ASN_CONFLICT": server_asn_conflict,
                                            "SERVER_ORG": server_meta["org"],
                                            "EXIT_ASN_IP_METADATA": exit_asn_ip_meta,
                                            "EXIT_ASN_RIPESTAT": exit_asn_ripestat,
                                            "EXIT_ASN_CONFLICT": exit_asn_conflict,
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
                    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
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
        "source": discovery_source,
        "discovery": discovery_meta,
        "selected_source": args.source,
        "selected_vpn_gate_ru_servers": len(selected),
        "requested_successful_ru_exits": args.max_servers,
        "max_connection_attempts": args.max_attempts,
        "connection_attempts": connection_counts["selected"],
        "successful_ru_exits": connection_counts["connected_ru_exit"],
        "usable_ru_openvpn_servers_discovered": len(servers),
        "provider_diversity_selection": selection_meta,
        "connection_counts": dict(connection_counts),
        "exit_geoip_categories": dict(exit_categories),
        "targets_in_ru_scope": len(targets),
        "target_measurements": len(measurement_rows),
        "geoip_candidates": len(candidates),
        "provider_rows": len(provider_rows),
        "server_asn_conflicts": sum(bool(row.get("SERVER_ASN_CONFLICT")) for row in provider_rows),
        "exit_asn_conflicts": sum(bool(row.get("EXIT_ASN_CONFLICT")) for row in provider_rows),
        "policy": {
            "vpn_gate_country_field_is_not_a_residential_attestation": True,
            "vpnobratno_site_listing_is_not_a_residential_attestation": True,
            "profile_variant_is_recorded_per_server_attempt": True,
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
    exit_code = measurement_exit_code(
        connection_counts["connected_ru_exit"], args.max_servers
    )
    if exit_code:
        print(
            f"measurement incomplete: verified {connection_counts['connected_ru_exit']} "
            f"of {args.max_servers} requested RU VPN exits",
            file=sys.stderr,
        )
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="GeoIP RU/PRIVATE inventory TSV")
    parser.add_argument("--targets", default=".github/reachability/targets.json")
    parser.add_argument("--output-dir", default="reachability-output")
    parser.add_argument(
        "--source", choices=("vpnobratno", "vpngate"), default="vpnobratno",
        help="Use VPNObratno's published profile variants or the official VPN Gate CSV API",
    )
    parser.add_argument("--max-servers", type=int, default=3, help="Number of successful RU VPN exits to measure")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum distinct VPN Gate candidates to try (hard cap 6)")
    parser.add_argument("--connect-timeout", type=int, default=60)
    parser.add_argument("--request-timeout", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.max_servers <= 6:
        parser.error("--max-servers must be between 1 and 6")
    if not args.max_servers <= args.max_attempts <= 6:
        parser.error("--max-attempts must be >= --max-servers and <=6")
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
        print(f"Russian VPN reachability error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
