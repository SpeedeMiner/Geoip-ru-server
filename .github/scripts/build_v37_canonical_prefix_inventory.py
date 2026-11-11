#!/usr/bin/env python3
"""Build a canonical exact-prefix inventory from immutable v37 release outputs.

The inventory keeps exact NLRI distinct: parent/child networks are never
collapsed together. It records final GeoIP output and retained derived evidence
layers, not unavailable raw upstream .dat inputs.
"""
from __future__ import annotations

import argparse
import csv
import ipaddress
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


CATEGORIES = {
    "ru": "output_ru",
    "private": "output_private",
}
SOURCE_FLAGS = (
    "output_ru",
    "output_private",
    "selected_origin_bgp",
    "rir_registered_ru",
    "global_bgp_90d",
    "additional_geoip_accepted",
    "blocked_approved",
    "blocked_review_only",
)
ASN_RE = re.compile(r"AS[0-9]+", re.IGNORECASE)


class InventoryError(ValueError):
    """Invalid input or inconsistent v37 source inventory."""


def _varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift >= 70:
            break
    raise InventoryError("truncated or overlong protobuf varint")


def _wire_fields(data: bytes) -> Iterable[tuple[int, int, object]]:
    offset = 0
    while offset < len(data):
        key, offset = _varint(data, offset)
        field_number, wire_type = key >> 3, key & 7
        if field_number == 0:
            raise InventoryError("protobuf field number 0 is invalid")
        if wire_type == 0:
            value, offset = _varint(data, offset)
        elif wire_type == 1:
            end = offset + 8
            if end > len(data):
                raise InventoryError("truncated fixed64 protobuf field")
            value, offset = data[offset:end], end
        elif wire_type == 2:
            length, offset = _varint(data, offset)
            end = offset + length
            if end > len(data):
                raise InventoryError("truncated length-delimited protobuf field")
            value, offset = data[offset:end], end
        elif wire_type == 5:
            end = offset + 4
            if end > len(data):
                raise InventoryError("truncated fixed32 protobuf field")
            value, offset = data[offset:end], end
        else:
            raise InventoryError(f"unsupported protobuf wire type {wire_type}")
        yield field_number, wire_type, value


def parse_cidr_message(data: bytes) -> str:
    raw_ip: bytes | None = None
    prefix: int | None = None
    for field, wire_type, value in _wire_fields(data):
        if field == 1 and wire_type == 2:
            raw_ip = value  # type: ignore[assignment]
        elif field == 2 and wire_type == 0:
            prefix = value  # type: ignore[assignment]
    if raw_ip is None or prefix is None:
        raise InventoryError("GeoIP CIDR message is missing ip or prefix")
    if len(raw_ip) not in (4, 16):
        raise InventoryError(f"GeoIP CIDR has invalid address byte length: {len(raw_ip)}")
    address = ipaddress.ip_address(raw_ip)
    maximum = 32 if address.version == 4 else 128
    if not 0 <= prefix <= maximum:
        raise InventoryError(f"GeoIP CIDR prefix length out of range: {prefix}")
    network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
    return network.with_prefixlen


def parse_geoip_list(data: bytes) -> dict[str, set[str]]:
    """Parse the Xray/V2Ray GeoIPList protobuf (entry=1, code=1, cidr=2)."""
    if not data:
        raise InventoryError("GeoIP protobuf is empty")
    result: dict[str, set[str]] = defaultdict(set)
    entries = 0
    for field, wire_type, value in _wire_fields(data):
        if field != 1 or wire_type != 2:
            continue
        entries += 1
        country_code = ""
        cidrs: list[str] = []
        for entry_field, entry_wire, entry_value in _wire_fields(value):  # type: ignore[arg-type]
            if entry_field == 1 and entry_wire == 2:
                try:
                    country_code = entry_value.decode("utf-8").strip().lower()  # type: ignore[union-attr]
                except UnicodeDecodeError as exc:
                    raise InventoryError("GeoIP country code is not UTF-8") from exc
            elif entry_field == 2 and entry_wire == 2:
                cidrs.append(parse_cidr_message(entry_value))  # type: ignore[arg-type]
        if not country_code:
            raise InventoryError("GeoIP entry has an empty country code")
        if country_code in CATEGORIES:
            result[country_code].update(cidrs)
    if entries == 0:
        raise InventoryError("GeoIP protobuf contains no GeoIPList entries")
    if not result.get("ru"):
        raise InventoryError("GeoIP protobuf has no RU entries")
    if not result.get("private"):
        raise InventoryError("GeoIP protobuf has no PRIVATE entries")
    return result


def _canonical_prefix(value: str, context: str) -> str:
    try:
        network = ipaddress.ip_network(value.strip(), strict=True)
    except ValueError as exc:
        raise InventoryError(f"{context}: invalid/non-canonical prefix {value!r}: {exc}") from exc
    if network.prefixlen == 0:
        raise InventoryError(f"{context}: default route is not accepted in a prefix evidence inventory")
    return network.with_prefixlen


def read_prefix_lines(path: Path, *, parse_origin_comments: bool = False) -> tuple[set[str], dict[str, set[str]]]:
    prefixes: set[str] = set()
    origins: dict[str, set[str]] = defaultdict(set)
    try:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        raise InventoryError(f"cannot read {path}: {exc}") from exc
    for line_no, raw in enumerate(lines, 1):
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        data, marker, comment = line.partition("#")
        token = data.strip().split()[0] if data.strip() else ""
        if not token:
            continue
        prefix = _canonical_prefix(token, f"{path}:{line_no}")
        prefixes.add(prefix)
        if parse_origin_comments and marker:
            origins[prefix].update(x.upper() for x in ASN_RE.findall(comment))
    return prefixes, origins


def read_tsv_prefixes(path: Path, column: str) -> tuple[set[str], dict[str, dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader((line for line in stream if not line.startswith("#")), delimiter="\t"))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise InventoryError(f"cannot read TSV {path}: {exc}") from exc
    if not rows or column not in rows[0]:
        raise InventoryError(f"{path}: missing rows or required {column} column")
    prefixes: set[str] = set()
    metadata: dict[str, dict[str, str]] = {}
    for line_no, row in enumerate(rows, 2):
        prefix = _canonical_prefix(row[column], f"{path}:{line_no}")
        prefixes.add(prefix)
        if prefix in metadata:
            # A repeated row is acceptable only if its source metadata is identical.
            if metadata[prefix] != row:
                raise InventoryError(f"{path}: duplicate prefix with conflicting metadata: {prefix}")
        else:
            metadata[prefix] = row
    return prefixes, metadata


def _sort_key(value: str) -> tuple[int, int, int]:
    net = ipaddress.ip_network(value)
    return net.version, int(net.network_address), net.prefixlen


def _address_union(prefixes: set[str], family: int) -> int:
    networks = [ipaddress.ip_network(value) for value in prefixes if ipaddress.ip_network(value).version == family]
    return sum(net.num_addresses for net in ipaddress.collapse_addresses(networks))


def build_inventory(args: argparse.Namespace) -> dict[str, object]:
    proto = parse_geoip_list(args.geoip_dat.read_bytes())
    ru_output, private_output = proto["ru"], proto["private"]
    selected_bgp, selected_origins = read_prefix_lines(args.selected_bgp, parse_origin_comments=True)
    rir_ru, _ = read_prefix_lines(args.rir_ru)
    global_bgp, _ = read_prefix_lines(args.global_bgp)
    blocked_approved, _ = read_prefix_lines(args.blocked_approved)

    additional, additional_rows = read_tsv_prefixes(args.additional_provenance, "PREFIX")
    blocked_review, _ = read_tsv_prefixes(args.blocked_review, "PREFIX")

    sets = {
        "output_ru": ru_output,
        "output_private": private_output,
        "selected_origin_bgp": selected_bgp,
        "rir_registered_ru": rir_ru,
        "global_bgp_90d": global_bgp,
        "additional_geoip_accepted": additional,
        "blocked_approved": blocked_approved,
        "blocked_review_only": blocked_review,
    }
    universe = set().union(*sets.values())
    sorted_prefixes = sorted(universe, key=_sort_key)

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "PREFIX", "FAMILY", "PREFIX_ADDRESSES",
        "IN_V37_RU_OUTPUT", "IN_V37_PRIVATE_OUTPUT",
        "IN_SELECTED_RIR_OR_COMPANY_ORIGIN_BGP", "SELECTED_ORIGIN_ASNS",
        "IN_RIR_RU_REGISTERED_RESOURCES",
        "IN_GLOBAL_BGP_90D_OBSERVATIONS",
        "IN_ACCEPTED_ADDITIONAL_GEOIP_FEEDS", "ADDITIONAL_LOGICAL_GROUPS",
        "IN_APPROVED_BLOCKED_EXCLUSIONS", "IN_BLOCKED_REVIEW_ONLY_CANDIDATES",
        "EXACT_PREFIX_INTERPRETATION",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for prefix in sorted_prefixes:
            network = ipaddress.ip_network(prefix)
            flags = {name: prefix in values for name, values in sets.items()}
            metadata = additional_rows.get(prefix, {})
            groups = metadata.get("GROUPS_WITH_OVERLAP", "")
            writer.writerow({
                "PREFIX": prefix,
                "FAMILY": f"IPv{network.version}",
                "PREFIX_ADDRESSES": network.num_addresses,
                "IN_V37_RU_OUTPUT": "yes" if flags["output_ru"] else "no",
                "IN_V37_PRIVATE_OUTPUT": "yes" if flags["output_private"] else "no",
                "IN_SELECTED_RIR_OR_COMPANY_ORIGIN_BGP": "yes" if flags["selected_origin_bgp"] else "no",
                "SELECTED_ORIGIN_ASNS": ",".join(sorted(selected_origins.get(prefix, set()))),
                "IN_RIR_RU_REGISTERED_RESOURCES": "yes" if flags["rir_registered_ru"] else "no",
                "IN_GLOBAL_BGP_90D_OBSERVATIONS": "yes" if flags["global_bgp_90d"] else "no",
                "IN_ACCEPTED_ADDITIONAL_GEOIP_FEEDS": "yes" if flags["additional_geoip_accepted"] else "no",
                "ADDITIONAL_LOGICAL_GROUPS": groups,
                "IN_APPROVED_BLOCKED_EXCLUSIONS": "yes" if flags["blocked_approved"] else "no",
                "IN_BLOCKED_REVIEW_ONLY_CANDIDATES": "yes" if flags["blocked_review_only"] else "no",
                "EXACT_PREFIX_INTERPRETATION": (
                    "CURRENT_RU_OUTPUT" if flags["output_ru"] else
                    "CURRENT_PRIVATE_OUTPUT" if flags["output_private"] else
                    "EVIDENCE_OR_CANDIDATE_ONLY"
                ),
            })

    stats_lines = [
        "v37 canonical exact-prefix inventory (review only)",
        f"Release commit: {args.release_commit}",
        f"GeoIP output SHA256: {args.geoip_sha256}",
        f"Unique exact prefixes in union inventory: {len(universe)}",
        f"IPv4 exact prefixes: {sum(ipaddress.ip_network(p).version == 4 for p in universe)}",
        f"IPv6 exact prefixes: {sum(ipaddress.ip_network(p).version == 6 for p in universe)}",
        "",
        "SOURCE_ID\tUNIQUE_EXACT_PREFIXES\tIPV4_PREFIXES\tIPV6_PREFIXES\tIPV4_ADDRESS_UNION\tIPV6_ADDRESS_UNION\tEXACT_MATCH_IN_RU_OUTPUT",
    ]
    for source_id, prefixes in sets.items():
        stats_lines.append(
            f"{source_id}\t{len(prefixes)}\t"
            f"{sum(ipaddress.ip_network(p).version == 4 for p in prefixes)}\t"
            f"{sum(ipaddress.ip_network(p).version == 6 for p in prefixes)}\t"
            f"{_address_union(prefixes, 4)}\t{_address_union(prefixes, 6)}\t"
            f"{len(prefixes & ru_output)}"
        )
    stats_lines.extend([
        "",
        f"Final RU output IPv4 address union: {_address_union(ru_output, 4)}",
        f"Final RU output IPv6 address union: {_address_union(ru_output, 6)}",
        f"Final PRIVATE output IPv4 address union: {_address_union(private_output, 4)}",
        f"Final PRIVATE output IPv6 address union: {_address_union(private_output, 6)}",
        f"Selected-origin BGP prefixes absent as exact CIDRs from RU output: {len(selected_bgp - ru_output)}",
        f"RU output exact CIDRs absent from selected-origin BGP: {len(ru_output - selected_bgp)}",
        f"RU output exact CIDRs also registered to RU in RIR stats: {len(ru_output & rir_ru)}",
        f"RU output exact CIDRs observed in global BGP 90-day snapshot: {len(ru_output & global_bgp)}",
        f"RU output exact CIDRs also in accepted additional feed provenance: {len(ru_output & additional)}",
        f"RU output exact CIDRs intersecting approved blocked list by exact CIDR: {len(ru_output & blocked_approved)}",
        "",
        "All joins are exact-prefix equality only. Parent/child CIDRs are not inferred as exact matches.",
        "Address unions are calculated per source after CIDR collapse; independent source totals overlap and must not be added.",
        "Selected-origin BGP is routing/operator evidence, not proof of physical location or legal ownership.",
        "RIR country is resource-registration country, not proof of physical hosting location.",
        "Global BGP comes from the pinned v37 ipverse 90-day observation archive; absence is not proof of route withdrawal.",
        "Additional-feed rows are the accepted per-prefix provenance table, not the complete raw source feed inventories.",
        "Raw GeoIP .dat inputs are not retained in the v37 release; category audit retains counts, not all exact raw feed CIDRs.",
        "Blocked review candidates are not production exclusions; only the approved blocked set is carved from DIRECT.",
        "No candidate is automatically added to or removed from production by this inventory.",
    ])
    args.stats.write_text("\n".join(stats_lines) + "\n", encoding="utf-8")
    return {
        "sets": sets,
        "prefixes": len(universe),
        "output_ru": len(ru_output),
        "output_private": len(private_output),
        "selected_bgp": len(selected_bgp),
        "rir_ru": len(rir_ru),
        "global_bgp": len(global_bgp),
        "additional": len(additional),
        "blocked_approved": len(blocked_approved),
        "blocked_review": len(blocked_review),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geoip-dat", type=Path, required=True)
    parser.add_argument("--selected-bgp", type=Path, required=True)
    parser.add_argument("--rir-ru", type=Path, required=True)
    parser.add_argument("--global-bgp", type=Path, required=True)
    parser.add_argument("--additional-provenance", type=Path, required=True)
    parser.add_argument("--blocked-approved", type=Path, required=True)
    parser.add_argument("--blocked-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--release-commit", required=True)
    parser.add_argument("--geoip-sha256", required=True)
    args = parser.parse_args()
    try:
        result = build_inventory(args)
    except (InventoryError, OSError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "Built v37 exact-prefix inventory: "
        + ", ".join(f"{key}={value}" for key, value in result.items() if key != "sets")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
