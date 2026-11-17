#!/usr/bin/env python3
"""Bounded exact endpoint observations and binding to one v41 release."""
from __future__ import annotations

from bisect import bisect_right
import http.client
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl

from validate_v41_publication_bounds import read as read_dat
from verify_v41_snapshot_replay import load_manifest, unique_object

HOST = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z")
TARGET_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
# Reject IANA special-purpose space, including special globally reachable
# exceptions that Python's is_global alone would otherwise admit.
SPECIAL = tuple(map(ipaddress.IPv4Network, (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24",
    "192.31.196.0/24", "192.52.193.0/24", "192.88.99.0/24", "192.168.0.0/16",
    "192.175.48.0/24", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24",
    "224.0.0.0/4", "240.0.0.0/4",
)))


def public_ipv4(value: object) -> ipaddress.IPv4Address:
    if not isinstance(value, str):
        raise ValueError("IPv4 must be a string")
    address = ipaddress.IPv4Address(value)
    if str(address) != value or not address.is_global or any(address in net for net in SPECIAL):
        raise ValueError("expected a canonical, non-special public IPv4")
    return address


def load_exact_targets(path: Path) -> list[dict]:
    with path.open("rb") as stream:
        raw = stream.read(8193)
    if not 0 < len(raw) <= 8192:
        raise ValueError("exact target JSON size must be 1–8192 bytes")
    data = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(data, list) or not 1 <= len(data) <= 6:
        raise ValueError("expected 1–6 explicit endpoints")
    result, ids, endpoints = [], set(), set()
    for item in data:
        if (not isinstance(item, dict) or set(item) - {"id", "ip", "prefix", "domain", "port"}
                or not {"id", "ip", "prefix"} <= item.keys()):
            raise ValueError("invalid exact target fields")
        ident, address, prefix = item["id"], public_ipv4(item["ip"]), item["prefix"]
        if not isinstance(ident, str) or not TARGET_ID.fullmatch(ident) or ident in ids:
            raise ValueError("invalid or duplicate target id")
        if not isinstance(prefix, str):
            raise ValueError("canonical IPv4 prefix required")
        network = ipaddress.IPv4Network(prefix, strict=True)
        if (str(network) != prefix or address not in network
                or any(network.overlaps(net) for net in SPECIAL)):
            raise ValueError("prefix must contain the point and not include special space")
        domain, port = item.get("domain", ""), item.get("port", 443)
        if not isinstance(domain, str) or (domain and not HOST.fullmatch(domain)):
            raise ValueError("invalid lowercase DNS hostname")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("invalid TCP port")
        key = (str(address), port, domain)
        if key in endpoints:
            raise ValueError("duplicate endpoint")
        ids.add(ident)
        endpoints.add(key)
        result.append({"id": ident, "ip": str(address), "prefix": prefix, "domain": domain, "port": port})
    return result


def range_at(intervals, address):
    ix = bisect_right(intervals, (int(address), 1 << address.max_prefixlen)) - 1
    return intervals[ix] if ix >= 0 and intervals[ix][1] >= int(address) else None


def bind_snapshot(directory: Path, release_commit: str, manifest_sha: str, targets: list[dict]) -> tuple[dict, list]:
    if not re.fullmatch(r"[0-9a-f]{40}", release_commit):
        raise ValueError("full immutable v41 release commit required")
    manifest_file = directory / "geoip_RU_v41_release_manifest.json"
    manifest = load_manifest(manifest_file, manifest_sha)
    dat = directory / "geoip_RU.dat"
    expected = manifest["assets"][dat.name]
    sidecar = directory / "geoip_RU.dat.sha256sum"
    with sidecar.open("rb") as stream:
        checksum = stream.read(256)
    size = dat.stat().st_size
    if size != expected["bytes"] or checksum != (expected["sha256"] + "  geoip_RU.dat\n").encode("ascii"):
        raise ValueError("v41 snapshot size or sidecar does not match pinned manifest")
    categories, digest = read_dat(dat)
    if digest != expected["sha256"]:
        raise ValueError("v41 DAT SHA-256 does not match pinned manifest")
    bound = []
    for t in targets:
        address = public_ipv4(t["ip"])
        membership = next((k for k in ("PRIVATE", "RU") if range_at(categories[k][4], address)), "OUTSIDE")
        bound.append({"id": t["id"], "geoip_category": membership})
    return {"release_commit": release_commit, "manifest_sha256": manifest_sha, "dat_sha256": digest,
            "source_commit": manifest["source_commit"]}, bound


def safe_dns(host: str) -> tuple[list, list]:
    rows = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    v4, v6 = set(), set()
    for family, _, _, _, endpoint in rows:
        address = ipaddress.ip_address(endpoint[0])
        if family == socket.AF_INET:
            try:
                v4.add(str(public_ipv4(str(address))))
            except ValueError:
                continue
        elif family == socket.AF_INET6 and address.is_global and not address.is_multicast:
            v6.add(str(address))
    return sorted(v4), sorted(v6)


def observation(target: dict) -> dict:
    return {**target, "dns": "NOT_TESTED", "tcp": "NOT_TESTED", "tls": "NOT_TESTED",
            "http": "NOT_TESTED", "dns_a": [], "dns_aaaa": [], "dns_matches_target": None,
            "http_status": None, "errors": {}, "ipv6_transport": "NOT_TESTED"}


def measure_exact(target, timeout, *, resolver=safe_dns, connect=socket.create_connection,
                  context=ssl.create_default_context, response=http.client.HTTPResponse):
    """No redirects; a received HTTP status is transport evidence only."""
    row = observation(target)
    host = target["domain"]
    if host:
        try:
            ipv4, ipv6 = resolver(host)
            row.update(dns="DNS_ANSWER" if ipv4 or ipv6 else "DNS_NO_ANSWER",
                       dns_a=ipv4, dns_aaaa=ipv6, dns_matches_target=target["ip"] in ipv4)
        except OSError as exc:
            row["dns"] = "PROBE_ERROR"
            row["errors"]["dns"] = type(exc).__name__
    sock = None
    try:
        try:
            sock = connect((target["ip"], target["port"]), timeout=timeout)
            row["tcp"] = "TCP_OK"
        except TimeoutError:
            row["tcp"] = "TCP_TIMEOUT"
            return row
        except OSError as exc:
            row["tcp"] = "PROBE_ERROR"
            row["errors"]["tcp"] = type(exc).__name__
            return row
        if not host:
            return row
        try:
            sock = context().wrap_socket(sock, server_hostname=host)
            row["tls"] = "TLS_OK"
        except (OSError, ValueError) as exc:
            row["tls"] = "PROBE_ERROR"
            row["errors"]["tls"] = type(exc).__name__
            return row
        try:
            authority = host if target["port"] == 443 else f"{host}:{target['port']}"
            sock.sendall((f"HEAD / HTTP/1.1\r\nHost: {authority}\r\n"
                          "User-Agent: GeoIP-v41-exact-probe\r\nConnection: close\r\n\r\n").encode("ascii"))
            with response(sock, method="HEAD") as resp:
                resp.begin()
                row.update(http="HTTP_OK", http_status=resp.status)
        except (OSError, http.client.HTTPException) as exc:
            row["http"] = "PROBE_ERROR"
            row["errors"]["http"] = type(exc).__name__
        return row
    finally:
        if sock is not None:
            sock.close()
