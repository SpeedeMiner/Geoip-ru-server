#!/usr/bin/env python3
"""Extract exact prefixes announced by the curated corporate ASN allowlist and RIR-RU ASNs."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import re
from pathlib import Path
from typing import Any

ASN_RE = re.compile(r"\bAS(\d+)\b", re.IGNORECASE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_company_asns(path: Path) -> dict[int, dict[str, str]]:
    result: dict[int, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for line_no, raw in enumerate(stream, 1):
            line = raw.rstrip("\r\n")
            if not line or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) != 4 or not all(value.strip() for value in fields):
                raise ValueError(f"Malformed company ASN registry line {line_no}: expected four non-empty TSV fields")
            token = fields[0].strip().upper()
            if token.startswith("AS"):
                token = token[2:]
            if not token.isdigit():
                raise ValueError(f"Invalid ASN on company registry line {line_no}: {fields[0]!r}")
            asn = int(token)
            if not 0 < asn <= 4294967295:
                raise ValueError(f"ASN out of range on company registry line {line_no}: {asn}")
            item = {"group": fields[1].strip(), "entity": fields[2].strip(), "evidence": fields[3].strip()}
            if asn in result and result[asn] != item:
                raise ValueError(f"Conflicting duplicate company ASN AS{asn}")
            result[asn] = item
    if len(result) < 10:
        raise ValueError(f"Company ASN allowlist unexpectedly small: {len(result)} entries")
    return result


def read_rir_ru_asns(path: Path, minimum: int = 10) -> set[int]:
    result: set[int] = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for line_no, raw in enumerate(stream, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            token = line.split()[0].strip().upper()
            if token.startswith("AS"):
                token = token[2:]
            if not token.isdigit():
                raise ValueError(f"Invalid RIR-RU ASN on line {line_no}: {line!r}")
            asn = int(token)
            if not 0 < asn <= 4294967295:
                raise ValueError(f"RIR-RU ASN out of range on line {line_no}: {asn}")
            result.add(asn)
    if len(result) < minimum:
        raise ValueError(f"RIR-RU ASN registry unexpectedly small: {len(result)} entries")
    return result


def build_company_prefixes(
    selected_prefixes: Path,
    company_registry: Path,
    output: Path,
    rir_ru_registry: Path | None = None,
) -> dict[str, Any]:
    companies = read_company_asns(company_registry)
    rir_ru_asns = read_rir_ru_asns(rir_ru_registry) if rir_ru_registry is not None else set()
    prefixes: dict[str, set[int]] = {}
    active_company_asns: set[int] = set()
    active_rir_ru_asns: set[int] = set()

    with selected_prefixes.open(encoding="utf-8-sig") as stream:
        for line_no, raw in enumerate(stream, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            prefix_token, marker, origins_text = line.partition("#")
            try:
                network = ipaddress.ip_network(prefix_token.strip(), strict=True)
            except ValueError as exc:
                raise ValueError(f"Invalid selected-origin prefix on line {line_no}: {prefix_token!r}") from exc
            if network.prefixlen == 0:
                raise ValueError(f"Default route is not allowed in selected-origin input: line {line_no}")
            if not marker:
                raise ValueError(f"Selected-origin line {line_no} has no origin-ASN provenance comment")
            origin_asns = {int(value) for value in ASN_RE.findall(origins_text)}
            if not origin_asns:
                raise ValueError(f"Selected-origin line {line_no} has no parseable AS-origin label")

            corporate = origin_asns & companies.keys()
            rir_ru = origin_asns & rir_ru_asns
            protected_origins = corporate | rir_ru
            if protected_origins:
                key = str(network)
                if key in prefixes:
                    raise ValueError(f"Duplicate selected-origin prefix: {key}")
                prefixes[key] = protected_origins
                active_company_asns.update(corporate)
                active_rir_ru_asns.update(rir_ru)

    if not prefixes:
        raise ValueError("No selected prefixes originate from the curated corporate or RIR-RU ASN sets")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("# v39 exact BGP prefixes whose origin set includes an ASN in geoip_RU_company_asns.txt or RIR-RU registry\n")
        stream.write("# Prefixes come from the same pinned ipverse archive-derived selected-origin input used by the v37 base build.\n")
        stream.write(f"# selected_origin_input_sha256={sha256(selected_prefixes)}\n")
        stream.write(f"# company_asn_registry_sha256={sha256(company_registry)}\n")
        if rir_ru_registry is not None:
            stream.write(f"# rir_ru_asn_registry_sha256={sha256(rir_ru_registry)}\n")
        for prefix in sorted(prefixes, key=lambda value: (
            ipaddress.ip_network(value).version,
            int(ipaddress.ip_network(value).network_address),
            ipaddress.ip_network(value).prefixlen,
        )):
            origin_label = ",".join(f"AS{asn}" for asn in sorted(prefixes[prefix]))
            stream.write(f"{prefix} # {origin_label}\n")

    counts = {4: 0, 6: 0}
    address_counts = {4: 0, 6: 0}
    active_asns: set[int] = set()
    for prefix, asns in prefixes.items():
        network = ipaddress.ip_network(prefix)
        counts[network.version] += 1
        address_counts[network.version] += network.num_addresses
        active_asns.update(asns)
    result: dict[str, Any] = {
        "company_asn_registry_entries": len(companies),
        "rir_ru_asn_registry_entries": len(rir_ru_asns),
        "active_company_asns": len(active_company_asns),
        "active_rir_ru_asns": len(active_rir_ru_asns),
        "active_protected_asns": len(active_asns),
        "unique_prefixes": len(prefixes),
        "ipv4_prefixes": counts[4],
        "ipv6_prefixes": counts[6],
        "ipv4_addresses": address_counts[4],
        "ipv6_addresses": address_counts[6],
        "selected_origin_input_sha256": sha256(selected_prefixes),
        "company_asn_registry_sha256": sha256(company_registry),
        "output_sha256": sha256(output),
    }
    if rir_ru_registry is not None:
        result["rir_ru_asn_registry_sha256"] = sha256(rir_ru_registry)
    print(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected-prefixes", type=Path, required=True)
    parser.add_argument("--company-asns", type=Path, required=True)
    parser.add_argument("--rir-ru-asns", type=Path, required=False, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_company_prefixes(args.selected_prefixes, args.company_asns, args.output, args.rir_ru_asns)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
