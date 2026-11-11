#!/usr/bin/env python3
"""Opt-in, local-only probe for a real household ISP connection.

Run this on a PC/router that is directly using the household ISP being tested.
The probe performs one DNS A/AAAA lookup and at most one HTTPS HEAD request per
address family for each declared hostname. It writes reports locally and never
uploads them. It does not scan networks, collect local/private IPs, inspect
traffic, or modify the host resolver/firewall.
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.client
import ipaddress
import json
import os
import pathlib
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import runner

USER_AGENT = "Geoip-ru-server-home-probe/1.0"
PROXY_ENV_NAMES = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
)
IP_METADATA_ENDPOINTS = (
    ("ipwho.is", "https://ipwho.is/"),
    ("ipapi.co", "https://ipapi.co/json/"),
)


class ProbeError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def proxy_environment(env: dict[str, str] | None = None) -> list[str]:
    values = os.environ if env is None else env
    return sorted(name for name in PROXY_ENV_NAMES if str(values.get(name, "")).strip())


def fetch_json(url: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = json.loads(response.read(1_000_000).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"{urllib.parse.urlparse(url).netloc}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProbeError(f"{urllib.parse.urlparse(url).netloc}: unexpected JSON")
    return payload


def parse_asn(value: Any) -> int:
    text = str(value or "").strip().upper()
    if text.startswith("AS"):
        text = text[2:]
    try:
        result = int(text)
    except (TypeError, ValueError):
        return 0
    return result if result > 0 else 0


def source_metadata(timeout: int) -> dict[str, Any]:
    """Collect public egress IP/country from two services; never block target tests."""
    observations: list[dict[str, Any]] = []
    errors: list[str] = []
    for provider, endpoint in IP_METADATA_ENDPOINTS:
        try:
            payload = fetch_json(endpoint, timeout)
            address = str(payload.get("ip") or "").strip()
            parsed = ipaddress.ip_address(address)
            if not parsed.is_global:
                raise ProbeError("reported address is not globally routable")
            connection = payload.get("connection") or {}
            country = str(payload.get("country_code") or payload.get("country") or "").upper()
            if len(country) != 2:
                raise ProbeError("response has no two-letter country code")
            asn = parse_asn(
                connection.get("asn")
                or payload.get("asn")
                or payload.get("org")
            )
            organization = str(
                connection.get("org")
                or connection.get("isp")
                or payload.get("org")
                or ""
            ).strip()
            observations.append({
                "provider": provider,
                "ip": str(parsed),
                "country": country,
                "asn": asn,
                "organization": organization,
            })
        except (ProbeError, ValueError) as exc:
            errors.append(str(exc))

    result: dict[str, Any] = {
        "observations": observations,
        "errors": errors,
        "verified": False,
        "status": "SOURCE_METADATA_UNVERIFIED",
        "public_ip": "",
        "country": "",
        "asn_candidates": sorted({item["asn"] for item in observations if item["asn"]}),
        "organizations": sorted({item["organization"] for item in observations if item["organization"]}),
    }
    if len(observations) >= 2:
        first = observations[0]
        if all(item["ip"] == first["ip"] and item["country"] == first["country"] for item in observations[1:]):
            result.update({
                "verified": True,
                "status": "TWO_SOURCE_CONSENSUS",
                "public_ip": first["ip"],
                "country": first["country"],
            })
        else:
            result["status"] = "SOURCE_METADATA_DISAGREEMENT"
    return result


def resolve_families(domain: str, port: int, timeout: int) -> dict[str, Any]:
    """Use the local system resolver: its answers are part of the ISP measurement."""
    previous_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        infos = socket.getaddrinfo(domain, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return {
            "ipv4_status": "DNS_ERROR",
            "ipv4_addresses": [],
            "ipv4_error": str(exc)[:300],
            "ipv6_status": "DNS_ERROR",
            "ipv6_addresses": [],
            "ipv6_error": str(exc)[:300],
        }
    except OSError as exc:
        error = str(exc)[:300]
        return {
            "ipv4_status": "DNS_ERROR",
            "ipv4_addresses": [],
            "ipv4_error": error,
            "ipv6_status": "DNS_ERROR",
            "ipv6_addresses": [],
            "ipv6_error": error,
        }
    finally:
        socket.setdefaulttimeout(previous_timeout)

    addresses: dict[str, set[str]] = {"ipv4": set(), "ipv6": set()}
    for family, _socktype, _proto, _canonname, sockaddr in infos:
        if family == socket.AF_INET:
            candidate = sockaddr[0]
            key = "ipv4"
        elif family == socket.AF_INET6:
            candidate = sockaddr[0]
            key = "ipv6"
        else:
            continue
        try:
            parsed = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if parsed.is_global:
            addresses[key].add(str(parsed))

    ipv4 = sorted(addresses["ipv4"])
    ipv6 = sorted(addresses["ipv6"])
    return {
        "ipv4_status": "DNS_ANSWER" if ipv4 else "DNS_NO_ANSWER",
        "ipv4_addresses": ipv4,
        "ipv4_error": "",
        "ipv6_status": "DNS_ANSWER" if ipv6 else "DNS_NO_ANSWER",
        "ipv6_addresses": ipv6,
        "ipv6_error": "",
    }


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to the DNS-observed IP while preserving hostname SNI/cert checks."""
    def __init__(self, hostname: str, address: str, port: int, timeout: int):
        super().__init__(hostname, port=port, timeout=timeout, context=ssl.create_default_context())
        self.pinned_address = address

    def connect(self) -> None:
        sock = socket.create_connection(
            (self.pinned_address, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def https_head_pinned(domain: str, address: str, port: int, path: str, timeout: int) -> tuple[str, int | None, str]:
    connection = None
    try:
        connection = PinnedHTTPSConnection(domain, address, port, timeout)
        connection.request(
            "HEAD",
            path,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        response.read(64_000)
        return "HTTP_RESPONSE", int(response.status), ""
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        return "INCONCLUSIVE", None, str(exc)[:300]
    finally:
        if connection is not None:
            connection.close()


def measure_target(target: dict[str, Any], timeout: int) -> dict[str, Any]:
    dns = resolve_families(target["domain"], int(target["port"]), timeout)
    ipv4_result, ipv4_status, ipv4_error = "NOT_TESTED", None, ""
    ipv6_result, ipv6_status, ipv6_error = "NOT_TESTED", None, ""

    # One deterministic address per family keeps request volume bounded.
    if dns["ipv4_addresses"]:
        ipv4_result, ipv4_status, ipv4_error = https_head_pinned(
            target["domain"], dns["ipv4_addresses"][0],
            int(target["port"]), target["path"], timeout,
        )
    if dns["ipv6_addresses"]:
        ipv6_result, ipv6_status, ipv6_error = https_head_pinned(
            target["domain"], dns["ipv6_addresses"][0],
            int(target["port"]), target["path"], timeout,
        )

    return {
        "observed_at": utc_now(),
        "source": "user_controlled_home_probe",
        "target_id": target["id"],
        "target_domain": target["domain"],
        "target_role": target["role"],
        "dns_ipv4_status": dns["ipv4_status"],
        "dns_ipv4_addresses": dns["ipv4_addresses"],
        "dns_ipv4_error": dns["ipv4_error"],
        "https_ipv4_result": ipv4_result,
        "https_ipv4_status": ipv4_status,
        "https_ipv4_error": ipv4_error,
        "dns_ipv6_status": dns["ipv6_status"],
        "dns_ipv6_addresses": dns["ipv6_addresses"],
        "dns_ipv6_error": dns["ipv6_error"],
        "https_ipv6_result": ipv6_result,
        "https_ipv6_status": ipv6_status,
        "https_ipv6_error": ipv6_error,
    }


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run_probe(args: argparse.Namespace) -> int:
    if not args.consent:
        raise ProbeError("explicit consent is required; pass --consent after reading the notice")
    proxy_vars = proxy_environment()
    if proxy_vars and not args.allow_proxy:
        raise ProbeError(
            "proxy environment variables are set (" + ", ".join(proxy_vars)
            + "); disable the proxy/VPN for a home-ISP test, or use --allow-proxy only if intentional"
        )

    targets = [
        target for target in runner.load_targets(pathlib.Path(args.targets))
        if args.required_country in target.get("country_scope", [])
    ]
    if args.max_targets is not None:
        targets = targets[:args.max_targets]
    if not targets:
        raise ProbeError("no targets are selected for this country")

    output = pathlib.Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    attribution = source_metadata(args.timeout)
    attribution["required_country"] = args.required_country
    if attribution["verified"] and attribution["country"] != args.required_country:
        attribution["status"] = "SOURCE_COUNTRY_MISMATCH"
    else:
        attribution["required_country_matches"] = (
            attribution["verified"] and attribution["country"] == args.required_country
        )

    rows = [measure_target(target, args.timeout) for target in targets]
    summary = {
        "generated_at": utc_now(),
        "probe_type": "USER_CONTROLLED_HOME_OR_ACCESS_NETWORK",
        "required_country": args.required_country,
        "source_attribution_status": attribution["status"],
        "source_ip_verified_by_two_services": attribution["verified"],
        "source_public_ip": attribution["public_ip"],
        "source_country": attribution["country"],
        "source_asn_candidates": attribution["asn_candidates"],
        "source_organizations": attribution["organizations"],
        "proxy_environment_variables": proxy_vars,
        "proxy_allowed_by_user": bool(args.allow_proxy),
        "target_count": len(targets),
        "service_targets": sum(target["role"] == "service" for target in targets),
        "control_targets": sum(target["role"] == "control" for target in targets),
        "https_ipv4_responses": sum(row["https_ipv4_result"] == "HTTP_RESPONSE" for row in rows),
        "https_ipv6_responses": sum(row["https_ipv6_result"] == "HTTP_RESPONSE" for row in rows),
        "dns_ipv4_answers": sum(row["dns_ipv4_status"] == "DNS_ANSWER" for row in rows),
        "dns_ipv6_answers": sum(row["dns_ipv6_status"] == "DNS_ANSWER" for row in rows),
        "automatic_upload": False,
        "geoip_mutation": False,
        "limitations": [
            "Run this script only on a network whose owner has explicitly consented, with commercial VPN/proxy disabled.",
            "A successful HTTP response proves transport/HTTP reachability only, not service health or absence of filtering.",
            "A DNS answer is not an HTTPS reachability result; IPv4 and IPv6 transport are recorded separately.",
            "IP country/ASN metadata is supporting attribution; it does not by itself prove a household subscriber line.",
            "The report contains the public egress IP and DNS answers; review it locally before sharing.",
            "No report is uploaded automatically and no credentials, cookies or user browsing data are collected.",
        ],
    }
    write_json(output / "home_probe_source.json", attribution)
    write_jsonl(output / "home_probe_measurements.jsonl", rows)
    write_json(output / "home_probe_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", default=".github/reachability/targets.json")
    parser.add_argument("--output-dir", default="home-probe-output")
    parser.add_argument("--required-country", choices=("RU", "KZ", "BY"), default="RU")
    parser.add_argument("--max-targets", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--consent", action="store_true", help="confirm authorization to test this network and the listed public endpoints")
    parser.add_argument("--allow-proxy", action="store_true", help="explicitly allow configured HTTP(S)_PROXY variables; not recommended for home-ISP attribution")
    args = parser.parse_args()
    if args.max_targets is not None and args.max_targets < 1:
        parser.error("--max-targets must be positive")
    if not 3 <= args.timeout <= 30:
        parser.error("--timeout must be between 3 and 30 seconds")
    try:
        return run_probe(args)
    except (OSError, ValueError, ProbeError, json.JSONDecodeError) as exc:
        print(f"Home probe error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
