"""Explicit, bounded exact-IP probes inside an already verified RU tunnel."""
from __future__ import annotations

import http.client
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
from typing import Any

HOST = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z")
ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")


def load_exact_targets(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if len(raw) > 8192:
        raise ValueError("exact target file exceeds 8192 bytes")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list) or not 1 <= len(data) <= 6:
        raise ValueError("exact targets must be an array of 1 to 6 explicit endpoints")
    result, ids, endpoints = [], set(), set()
    for item in data:
        if not isinstance(item, dict) or set(item) - {"id", "ip", "prefix", "domain", "port"}:
            raise ValueError("unexpected exact target fields")
        ident, value, prefix = item.get("id"), item.get("ip"), item.get("prefix")
        if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in ids:
            raise ValueError("invalid or duplicate exact target id")
        if not isinstance(value, str) or not isinstance(prefix, str):
            raise ValueError("exact IPv4 and canonical prefix are required")
        ip = ipaddress.ip_address(value)
        network = ipaddress.ip_network(prefix, strict=True)
        if ip.version != 4 or network.version != 4:
            raise ValueError("IPv6 is not supported by the isolated VPN tunnel")
        if str(ip) != value or str(network) != prefix or not ip.is_global or ip.is_multicast or ip not in network:
            raise ValueError("target must be a global IPv4 inside the declared canonical prefix")
        domain = item.get("domain", "")
        if not isinstance(domain, str) or (domain and not HOST.fullmatch(domain)):
            raise ValueError("domain must be a lowercase DNS hostname, or empty for TCP-only")
        port = item.get("port", 443)
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("port must be an integer between 1 and 65535")
        if (value, port, domain) in endpoints:
            raise ValueError("duplicate endpoint")
        ids.add(ident)
        endpoints.add((value, port, domain))
        result.append({"id": ident, "ip": value, "prefix": prefix, "domain": domain, "port": port})
    return result


def measure_exact(target: dict[str, Any], exit_info: dict[str, Any], timeout: int, resolver: Any, observed_at: str) -> dict[str, Any]:
    """One TCP connection; optionally verify TLS/SNI and request HEAD on that socket."""
    if exit_info.get("country") != "RU":
        raise ValueError("exact endpoint probes require a verified RU exit")
    host = target["domain"]
    row = {
        "SOURCE": "vpn_gate", "OBSERVED_AT": observed_at,
        "TARGET_ID": target["id"], "TARGET_DOMAIN": host, "TARGET_IP": target["ip"],
        "EXPECTED_PREFIX": target["prefix"], "TARGET_PORT": target["port"],
        "PROBE_MODE": "EXACT_IPV4", "DNS_RESULT": "NOT_REQUESTED", "DNS_A_ADDRESSES": [],
        "DNS_AAAA_RESULT": "NOT_REQUESTED", "DNS_AAAA_ADDRESSES": [],
        "DNS_MATCHES_TARGET": None, "TCP_RESULT": "NOT_TESTED", "TLS_RESULT": "NOT_TESTED",
        "HTTPS_RESULT": "NOT_TESTED", "HTTP_STATUS": None, "ERROR": "",
        "EXIT_IP": exit_info["ip"], "EXIT_COUNTRY": exit_info["country"],
        "EXIT_ASN": exit_info["asn"], "EXIT_ORG": exit_info["org"],
        "ACCESS_NETWORK_TYPE": "UNVERIFIED", "IPV6_TRANSPORT": "NOT_TESTED_TUNNEL_IPV4_ONLY",
    }
    if host:
        (status, addresses, error), (aaaa_status, aaaa_addresses, aaaa_error) = resolver(host, timeout)
        row.update(DNS_RESULT=status, DNS_A_ADDRESSES=addresses,
                   DNS_AAAA_RESULT=aaaa_status, DNS_AAAA_ADDRESSES=aaaa_addresses,
                   DNS_MATCHES_TARGET=(target["ip"] in addresses) if status == "DNS_ANSWER" else None)
        if error:
            row["ERROR"] = "DNS: " + str(error)[:180]
        if aaaa_error and aaaa_error != error:
            row["ERROR"] = (row["ERROR"] + " | DNS AAAA: " + str(aaaa_error)[:180]).strip(" |")
    sock = None
    try:
        sock = socket.create_connection((target["ip"], target["port"]), timeout=timeout)
        sock.settimeout(timeout)
        row["TCP_RESULT"] = "CONNECTED"
        if not host:
            return row
        try:
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            row["TLS_RESULT"] = "VERIFIED"
        except (OSError, ssl.SSLError) as exc:
            row["TLS_RESULT"] = "INCONCLUSIVE"
            row["ERROR"] = (row["ERROR"] + " | TLS: " + str(exc)[:180]).strip(" |")
            return row
        try:
            request = f"HEAD / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Geoip-ru-server-exact-probe/1.0\r\nConnection: close\r\n\r\n"
            sock.sendall(request.encode("ascii"))
            response = http.client.HTTPResponse(sock)
            response.begin()
            row["HTTPS_RESULT"] = "HTTP_RESPONSE"
            row["HTTP_STATUS"] = response.status
        except (OSError, http.client.HTTPException) as exc:
            row["HTTPS_RESULT"] = "INCONCLUSIVE"
            row["ERROR"] = (row["ERROR"] + " | HTTP: " + str(exc)[:180]).strip(" |")
    except OSError as exc:
        row["TCP_RESULT"] = "INCONCLUSIVE"
        row["ERROR"] = (row["ERROR"] + " | TCP: " + str(exc)[:180]).strip(" |")
    finally:
        if sock is not None:
            sock.close()
    return row
