#!/usr/bin/env python3
"""Build a canonical exact-prefix inventory from immutable v37 release outputs.

The inventory keeps exact NLRI distinct: parent/child networks are never
collapsed together. It records final GeoIP output and retained derived evidence
layers, not unavailable raw upstream .dat inputs.
"""
from __future__ import annotations

import argparse
import bisect
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


def read_tsv_prefixes(
    path: Path, column: str, *, allow_duplicate_prefixes: bool = False
) -> tuple[set[str], dict[str, dict[str, str]]]:
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
            if not allow_duplicate_prefixes and metadata[prefix] != row:
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


def _merged_intervals(prefixes: set[str], family: int) -> list[tuple[int, int]]:
    intervals = sorted(
        (int(net.network_address), int(net.broadcast_address))
        for value in prefixes
        if (net := ipaddress.ip_network(value)).version == family
    )
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1] + 1:
            if end > merged[-1][1]:
                merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _intersection_size(left: list[tuple[int, int]], right: list[tuple[int, int]]) -> int:
    i = j = total = 0
    while i < len(left) and j < len(right):
        start = max(left[i][0], right[j][0])
        end = min(left[i][1], right[j][1])
        if start <= end:
            total += end - start + 1
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return total


def _subtract_intervals(
    source: list[tuple[int, int]], covered: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    remaining: list[tuple[int, int]] = []
    j = 0
    for start, end in source:
        cursor = start
        while j < len(covered) and covered[j][1] < cursor:
            j += 1
        k = j
        while k < len(covered) and covered[k][0] <= end:
            covered_start, covered_end = covered[k]
            if covered_start > cursor:
                remaining.append((cursor, min(end, covered_start - 1)))
            cursor = max(cursor, covered_end + 1)
            if cursor > end:
                break
            k += 1
        if cursor <= end:
            remaining.append((cursor, end))
    return remaining


def _interval_size(intervals: list[tuple[int, int]]) -> int:
    return sum(end - start + 1 for start, end in intervals)


def _covered_addresses(
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
    starts: list[int],
    ends: list[int],
) -> int:
    start = int(network.network_address)
    end = int(network.broadcast_address)
    index = bisect.bisect_left(ends, start)
    total = 0
    while index < len(starts) and starts[index] <= end:
        overlap_start = max(start, starts[index])
        overlap_end = min(end, ends[index])
        if overlap_start <= overlap_end:
            total += overlap_end - overlap_start + 1
        index += 1
    return total


def _percent(numerator: int, denominator: int) -> str:
    return "n/a" if denominator == 0 else f"{100 * numerator / denominator:.6f}%"


def build_inventory(args: argparse.Namespace) -> dict[str, object]:
    proto = parse_geoip_list(args.geoip_dat.read_bytes())
    ru_output, private_output = proto["ru"], proto["private"]
    selected_bgp, selected_origins = read_prefix_lines(args.selected_bgp, parse_origin_comments=True)
    rir_ru, _ = read_prefix_lines(args.rir_ru)
    global_bgp, _ = read_prefix_lines(args.global_bgp)
    blocked_approved, _ = read_prefix_lines(args.blocked_approved)

    additional, additional_rows = read_tsv_prefixes(args.additional_provenance, "PREFIX")
    # The same blocked candidate may be suggested independently by multiple sources.
    # This inventory records one exact CIDR flag; the original multi-source rows remain
    # available in the untouched TSV and must not be collapsed there.
    blocked_review, _ = read_tsv_prefixes(
        args.blocked_review, "PREFIX", allow_duplicate_prefixes=True
    )

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
    ru_merged = {family: _merged_intervals(ru_output, family) for family in (4, 6)}
    policy_prefixes = ru_output | private_output | blocked_approved
    policy_merged = {family: _merged_intervals(policy_prefixes, family) for family in (4, 6)}
    private_merged = {family: _merged_intervals(private_output, family) for family in (4, 6)}
    blocked_merged = {family: _merged_intervals(blocked_approved, family) for family in (4, 6)}
    ru_starts = {family: [start for start, _ in ru_merged[family]] for family in (4, 6)}
    ru_ends = {family: [end for _, end in ru_merged[family]] for family in (4, 6)}
    private_starts = {family: [start for start, _ in private_merged[family]] for family in (4, 6)}
    private_ends = {family: [end for _, end in private_merged[family]] for family in (4, 6)}
    blocked_starts = {family: [start for start, _ in blocked_merged[family]] for family in (4, 6)}
    blocked_ends = {family: [end for _, end in blocked_merged[family]] for family in (4, 6)}
    policy_starts = {family: [start for start, _ in policy_merged[family]] for family in (4, 6)}
    policy_ends = {family: [end for _, end in policy_merged[family]] for family in (4, 6)}

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
        "RU_OUTPUT_COVERED_ADDRESSES", "RU_OUTPUT_ADDRESS_COVERAGE",
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
            covered_addresses = _covered_addresses(
                network, ru_starts[network.version], ru_ends[network.version]
            )
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
                "RU_OUTPUT_COVERED_ADDRESSES": covered_addresses,
                "RU_OUTPUT_ADDRESS_COVERAGE": (
                    "NONE" if covered_addresses == 0 else
                    "FULL" if covered_addresses == network.num_addresses else
                    "PARTIAL"
                ),
                "EXACT_PREFIX_INTERPRETATION": (
                    "CURRENT_RU_OUTPUT" if flags["output_ru"] else
                    "CURRENT_PRIVATE_OUTPUT" if flags["output_private"] else
                    "EVIDENCE_OR_CANDIDATE_ONLY"
                ),
            })

    rir_residual_rows: list[dict[str, object]] = []
    for prefix in sorted(rir_ru, key=_sort_key):
        network = ipaddress.ip_network(prefix)
        family = network.version
        ru_covered = _covered_addresses(network, ru_starts[family], ru_ends[family])
        private_covered = _covered_addresses(network, private_starts[family], private_ends[family])
        blocked_covered = _covered_addresses(network, blocked_starts[family], blocked_ends[family])
        policy_covered = _covered_addresses(network, policy_starts[family], policy_ends[family])
        unexplained = network.num_addresses - policy_covered
        if unexplained <= 0:
            continue
        rir_residual_rows.append({
            "PREFIX": prefix,
            "FAMILY": f"IPv{family}",
            "PREFIX_ADDRESSES": network.num_addresses,
            "RU_OUTPUT_COVERED_ADDRESSES": ru_covered,
            "PRIVATE_COVERED_ADDRESSES": private_covered,
            "APPROVED_BLOCKED_COVERED_ADDRESSES": blocked_covered,
            "POLICY_COVERED_ADDRESSES": policy_covered,
            "UNEXPLAINED_OUTSIDE_RU_PRIVATE_BLOCKED_ADDRESSES": unexplained,
            "STATUS": "REVIEW",
            "DECISION_NOTE": "RIR country is registration metadata only; requires exact BGP/GeoIP/resource-holder evidence before any production decision.",
        })
    args.rir_residual_output.parent.mkdir(parents=True, exist_ok=True)
    residual_fields = [
        "PREFIX", "FAMILY", "PREFIX_ADDRESSES",
        "RU_OUTPUT_COVERED_ADDRESSES", "PRIVATE_COVERED_ADDRESSES",
        "APPROVED_BLOCKED_COVERED_ADDRESSES", "POLICY_COVERED_ADDRESSES",
        "UNEXPLAINED_OUTSIDE_RU_PRIVATE_BLOCKED_ADDRESSES", "STATUS", "DECISION_NOTE",
    ]
    with args.rir_residual_output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=residual_fields, delimiter="\\t", lineterminator="\\n")
        writer.writeheader()
        writer.writerows(rir_residual_rows)

    residual_union = {
        family: _subtract_intervals(
            _merged_intervals(rir_ru, family), policy_merged[family]
        )
        for family in (4, 6)
    }
    residual_family_counts = {
        family: sum(row["FAMILY"] == f"IPv{family}" for row in rir_residual_rows)
        for family in (4, 6)
    }

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
        "ADDRESS-SPACE COVERAGE BY RU OUTPUT (interval intersection; separate from exact CIDR equality)",
    ])
    for source_id, prefixes in sets.items():
        for family in (4, 6):
            source_union = _merged_intervals(prefixes, family)
            covered = _intersection_size(source_union, ru_merged[family])
            total = _address_union(prefixes, family)
            stats_lines.append(
                f"{source_id} IPv{family}: address_union={total}; covered_by_RU_output={covered}; "
                f"coverage={_percent(covered, total)}; outside_RU_output={total-covered}"
            )
    stats_lines.extend([
        "",
        "SELECTED-ORIGIN / RIR RESOURCE RESIDUAL AFTER RU + PRIVATE + APPROVED BLOCKED",
    ])
    for source_id in ("selected_origin_bgp", "rir_registered_ru"):
        prefixes = sets[source_id]
        for family in (4, 6):
            source_union = _merged_intervals(prefixes, family)
            total = _address_union(prefixes, family)
            covered_ru = _intersection_size(source_union, ru_merged[family])
            covered_policy = _intersection_size(source_union, policy_merged[family])
            outside_ru = total - covered_ru
            unexplained = total - covered_policy
            covered_by_other_policy = outside_ru - unexplained
            stats_lines.append(
                f"{source_id} IPv{family}: address_union={total}; covered_by_RU_output={covered_ru}; "
                f"outside_RU_output={outside_ru}; covered_outside_RU_by_PRIVATE_or_approved_BLOCKED="
                f"{covered_by_other_policy}; unexplained_outside_RU_PRIVATE_BLOCKED={unexplained}"
            )
    stats_lines.extend([
        "",
        f"RIR RU resource residual review rows: {len(rir_residual_rows)}; "
        f"IPv4={residual_family_counts[4]}; IPv6={residual_family_counts[6]}; all STATUS=REVIEW",
        f"RIR RU resource unique IPv4 address residual outside RU+PRIVATE+approved BLOCKED: "
        f"{_interval_size(residual_union[4])}",
        f"RIR RU resource unique IPv6 address residual outside RU+PRIVATE+approved BLOCKED: "
        f"{_interval_size(residual_union[6])}",
        "Residual review rows retain exact RIR resource prefixes; row address counts may overlap and are not additive.",
        "",
        f"Approved blocked exclusions overlapping RU output IPv4 addresses: "
        f"{_intersection_size(_merged_intervals(blocked_approved, 4), ru_merged[4])}",
        f"Approved blocked exclusions overlapping RU output IPv6 addresses: "
        f"{_intersection_size(_merged_intervals(blocked_approved, 6), ru_merged[6])}",
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
        "Exact-prefix flags use canonical CIDR string equality only; parent/child routes are not inferred as exact NLRI matches.",
        "RU_OUTPUT_COVERED_ADDRESSES and ADDRESS_COVERAGE add separate interval-based address-space intersection; they do not alter exact-prefix identity.",
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
        "rir_residual_review": len(rir_residual_rows),
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
    parser.add_argument("--rir-residual-output", type=Path, required=True)
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
