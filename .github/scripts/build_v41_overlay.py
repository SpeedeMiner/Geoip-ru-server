#!/usr/bin/env python3
"""Assemble the v41 unified DIRECT RU+BY+KZ GeoIP overlay.

v41 keeps selected origins and registered regional resources DIRECT against DNS
and unverified legacy exclusions. Hard IP/subnet evidence and Telegram still win.
PRIVATE retains absolute precedence. Output remains RU and PRIVATE.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
import csv
import hashlib
import ipaddress
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from validate_v41_telegram import PINNED_FEED, read_telegram_feed

SOURCE_REFS = {
    "kyoresuas-standard": {
        "repository": "kyoresuas/ru-direct",
        "commit": "0781793a159f9a53c5e68da2f46b0a64855f8cb6",
        "files": ["ru-standard.ipv4.txt", "ru-standard.ipv6.txt", "services.json"],
        "license": "Owner waived separate license verification; preserve upstream data attributions",
    },
    "w1zardz-service-direct": {
        "repository": "w1zardz/amnezia-vpn-russia-split-tunneling",
        "commit": "6157cdfb55f1748c98cab121cde008b5f69d325d",
        "files": ["dist/ru-direct-ipv4.txt"],
        "license": "MIT",
    },
    "hxehex-mobile-hosts": {
        "repository": "hxehex/russia-mobile-internet-whitelist",
        "commit": "fad3653ebd4b212643774a4d10af3eb33838e4ff",
        "files": ["ipwhitelist.txt"],
        "license": "MIT",
    },
    "operator-whitelist": {
        "repository": "escapingworm/russia-whitelist",
        "commit": "2bb6c0788f21986b7928d986ea2577c6ebc11b36",
        "files": ["ru-whitelist-cidr.txt"],
        "license": "MIT",
    },
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def parse_network(token: str, host_to_32: bool = True):
    token = token.strip().strip('"').strip("'").strip("[](){}")
    if not token:
        raise ValueError("empty network token")
    if "/" in token:
        return ipaddress.ip_network(token, strict=True)
    if not host_to_32:
        raise ValueError("explicit CIDR prefix length required")
    address = ipaddress.ip_address(token)
    return ipaddress.ip_network((address, address.max_prefixlen), strict=True)

def parse_cidr_file(path: Path, allow_hosts: bool = True):
    networks = set()
    raw = invalid = 0
    for line_no, original in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        upper = line.upper()
        for marker in ("IP-CIDR6,", "IP-CIDR,", "CIDR,", "IPSET,"):
            if upper.startswith(marker):
                line = line[len(marker):].strip()
                break
        values = line.replace(",", " ").replace(";", " ").split()
        found = None
        # The first field is the address. Do not accept a different address
        # in trailing metadata after an invalid primary field.
        if values:
            try:
                found = parse_network(values[0], allow_hosts)
            except ValueError:
                pass
        if found is None:
            invalid += 1
            continue
        if found.prefixlen == 0:
            invalid += 1
            continue
        raw += 1
        networks.add(found)
    if not networks:
        raise ValueError(f"source {path} contains no valid CIDRs")
    if invalid > max(20, int((raw + invalid) * 0.01)):
        raise ValueError(f"source {path} has too many invalid rows: {invalid}")
    return networks, {"raw_rows": raw + invalid, "valid_rows": raw, "invalid_rows": invalid}

def parse_reviewed_operator_prefixes(path: Path):
    """Read exact reviewed prefixes without conferring ASN-level trust."""
    rows = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["country", "prefix", "origin_asn"]:
            raise ValueError(f"{path}: unexpected reviewed operator prefix header")
        for row in reader:
            try:
                country, token, asn = (row[key] for key in reader.fieldnames)
                if None in row or country not in ("RU", "BY", "KZ") or not token or not asn:
                    raise ValueError
                network = ipaddress.ip_network(token, strict=True)
                minimum = 23 if network.version == 4 else 64
                if (token != str(network) or network.prefixlen < minimum
                        or not network.is_global or network.is_multicast
                        or getattr(network.network_address, "ipv4_mapped", None) is not None):
                    raise ValueError
                if not asn.startswith("AS") or not asn[2:].isascii() or not asn[2:].isdigit():
                    raise ValueError
                number = int(asn[2:])
                if asn != f"AS{number}" or not 1 <= number <= 4294967295:
                    raise ValueError
                if any(network.version == other.version and network.overlaps(other) for other in rows):
                    raise ValueError
            except ValueError as error:
                raise ValueError(f"{path}:{reader.line_num}: invalid reviewed operator prefix row") from error
            rows[network] = (country, asn)
            if len(rows) > 32:
                raise ValueError(f"{path}: too many reviewed operator prefixes")
    if not rows:
        raise ValueError(f"{path}: empty reviewed operator prefix list")
    return rows


def reviewed_operator_provenance(reviewed, source_id):
    ordered = sorted(reviewed, key=lambda net: (net.version, int(net.network_address), net.prefixlen))
    return [{"source_id": source_id, "category": reviewed[net][0],
             "service": "", "tier": "", "asn_list": reviewed[net][1], "domains": "",
             "prefix": str(net)} for net in ordered]


def parse_regional_admission_exclusions(path: Path):
    """Load reviewed exact prefixes, not ASN-wide or rolling geographic exclusions."""
    rows = {}
    header = ["prefix", "delegated_country", "assignment_country", "origin_asn", "checked_on"]
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != header:
            raise ValueError(f"{path}: invalid regional admission exclusions header")
        for row in reader:
            try:
                prefix, delegated, assignment, asn, checked = (row[key] for key in header)
                if None in row or not all((prefix, delegated, assignment, asn, checked)):
                    raise ValueError
                net = ipaddress.ip_network(prefix, strict=True)
                if (net.version != 4 or str(net) != prefix or net.prefixlen < 16
                        or not net.is_global or net.is_multicast
                        or delegated not in {"RU", "BY", "KZ"}
                        or not re.fullmatch(r"[A-Z]{2}", assignment)
                        or assignment in {"RU", "BY", "KZ"}
                        or not re.fullmatch(r"AS[1-9][0-9]{0,9}", asn)
                        or int(asn[2:]) > 4294967295
                        or date.fromisoformat(checked).isoformat() != checked
                        or any(net.overlaps(other) for other in rows)):
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{path}:{reader.line_num}: invalid regional admission exclusion") from exc
            rows[net] = {key: row[key] for key in header}
    return rows


def assert_regional_admission_disjoint(ru, exclusions):
    for v in (4, 6):
        if intersect(intervals(ru, v), intervals(exclusions, v)):
            raise ValueError(f"IPv{v} DIRECT intersects reviewed regional admission exclusions")


def parse_rir_tsv(path: Path):
    result = defaultdict(set)
    records = 0
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"country", "prefix", "registry", "status"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("RIR RU+BY+KZ TSV has an unexpected schema")
        for row in reader:
            country = row["country"].upper()
            net = ipaddress.ip_network(row["prefix"], strict=True)
            if country not in {"RU", "BY", "KZ"} or net.prefixlen == 0:
                raise ValueError(f"invalid RIR row: {row}")
            result[country].add(net)
            records += 1
    if not all(result[c] for c in ("RU", "BY", "KZ")):
        missing = [c for c in ("RU", "BY", "KZ") if not result[c]]
        raise ValueError("RIR inventory is missing countries: " + ",".join(missing))
    return result, records

def parse_services_json(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    categories = doc.get("categories")
    if not isinstance(categories, list):
        raise ValueError("Kyoresuas services.json does not contain categories[]")
    networks = set()
    rows = []
    service_count = 0
    for category in categories:
        if not isinstance(category, dict):
            continue
        category_id = str(category.get("id", "unknown"))
        for service in category.get("services", []) or []:
            if not isinstance(service, dict):
                continue
            tier = str(service.get("tier", "")).lower()
            if tier not in {"lite", "standard"}:
                continue
            service_count += 1
            name = str(service.get("name", "unknown")).replace("\t", " ").replace("\n", " ")
            asns = ",".join(str(x) for x in service.get("asns", []) or [])
            domains = int(service.get("domains", 0) or 0)
            for family_key in ("ipv4", "ipv6"):
                for token in service.get(family_key, []) or []:
                    net = ipaddress.ip_network(str(token), strict=True)
                    expected_version = 4 if family_key == "ipv4" else 6
                    if net.version != expected_version:
                        raise ValueError(f"Kyoresuas service family mismatch: {name} {token}")
                    networks.add(net)
                    rows.append({
                        "source_id": "kyoresuas-standard",
                        "category": category_id,
                        "service": name,
                        "tier": tier,
                        "asn_list": asns,
                        "domains": str(domains),
                        "prefix": str(net),
                    })
    if service_count == 0 or not networks:
        raise ValueError("Kyoresuas service catalog is empty or has no valid prefixes")
    return networks, rows, service_count, doc.get("generatedAt")

def read_varint(data: bytes, offset: int):
    value = shift = 0
    while True:
        if offset >= len(data) or shift >= 70:
            raise ValueError("malformed protobuf varint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7

def protobuf_fields(data: bytes):
    offset = 0
    while offset < len(data):
        key, offset = read_varint(data, offset)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise ValueError("protobuf field number 0")
        if wire == 0:
            value, offset = read_varint(data, offset)
        elif wire == 1:
            value = data[offset:offset+8]
            offset += 8
        elif wire == 2:
            length, offset = read_varint(data, offset)
            value = data[offset:offset+length]
            if len(value) != length:
                raise ValueError("truncated protobuf length-delimited field")
            offset += length
        elif wire == 5:
            value = data[offset:offset+4]
            offset += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        if wire in (1, 2, 5) and len(value) != (8 if wire == 1 else 4 if wire == 5 else len(value)):
            raise ValueError("truncated protobuf fixed-width field")
        yield number, wire, value

def parse_geoip_dat(path: Path):
    result = {}
    data = path.read_bytes()
    for number, wire, entry in protobuf_fields(data):
        if number != 1 or wire != 2:
            continue
        category = None
        networks = set()
        inverse_seen = False
        for en, ew, ev in protobuf_fields(entry):
            if en == 1 and ew == 2:
                if category is not None:
                    raise ValueError("duplicate GeoIP category field")
                category = ev.decode("ascii").upper()
            elif en == 2 and ew == 2:
                address = prefix = None
                for cn, cw, cv in protobuf_fields(ev):
                    if cn == 1 and cw == 2:
                        if address is not None:
                            raise ValueError("duplicate GeoIP address field")
                        address = cv
                    elif cn == 2 and cw == 0:
                        if prefix is not None:
                            raise ValueError("duplicate GeoIP prefix field")
                        prefix = int(cv)
                if address is not None and prefix is not None:
                    ip = ipaddress.ip_address(address)
                    networks.add(ipaddress.ip_network((ip, prefix), strict=True))
                else:
                    raise ValueError("invalid GeoIP CIDR: missing IP or prefix")
            elif en == 3:
                if ew != 0 or ev != 0 or inverse_seen:
                    raise ValueError("inverted or malformed GeoIP categories are unsupported")
                inverse_seen = True
        if not category or category in result:
            raise ValueError("missing or duplicate GeoIP category")
        result[category] = networks
    if not result:
        raise ValueError("base GeoIP protobuf has no categories")
    return result

def parse_hydra_direct_whitelist(path: Path):
    """Hydra routing-intent categories; PRIVATE and v41 blocks still take precedence."""
    categories = parse_geoip_dat(path)
    if not {"DIRECT", "WHITELIST"}.issubset(categories):
        raise ValueError("Hydra GeoIP is missing DIRECT or WHITELIST category")
    direct, whitelist = categories["DIRECT"], categories["WHITELIST"]
    if not direct or not whitelist:
        raise ValueError("Hydra DIRECT/WHITELIST cannot be empty")
    if any(net.prefixlen < (8 if net.version == 4 else 24) for net in direct | whitelist):
        raise ValueError("Hydra DIRECT/WHITELIST contains a default route or overly broad prefix")
    return {"hydra-direct": direct, "hydra-whitelist": whitelist}


def hydra_expected_after_policy(hydra_sources, private, blocked):
    """Exact address-space set of Hydra candidates eligible for DIRECT."""
    return subtract_networks(union_networks(*hydra_sources.values()), private, blocked)


def encode_varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)

def field_varint(number: int, value: int) -> bytes:
    return encode_varint(number << 3) + encode_varint(value)

def field_bytes(number: int, value: bytes) -> bytes:
    return encode_varint((number << 3) | 2) + encode_varint(len(value)) + value

def collapse(networks: Iterable[ipaddress._BaseNetwork]):
    result = []
    for version in (4, 6):
        result.extend(ipaddress.collapse_addresses(n for n in networks if n.version == version))
    return sorted(result, key=lambda n: (n.version, int(n.network_address), n.prefixlen))

def encode_geoip(entries: dict[str, set[ipaddress._BaseNetwork]]) -> bytes:
    result = bytearray()
    for category in sorted(entries):
        networks = collapse(entries[category])
        entry = bytearray(field_bytes(1, category.encode("ascii")))
        for net in networks:
            cidr = field_bytes(1, net.network_address.packed) + field_varint(2, net.prefixlen)
            entry.extend(field_bytes(2, cidr))
        result.extend(field_bytes(1, bytes(entry)))
    return bytes(result)

def intervals(networks: Iterable[ipaddress._BaseNetwork], version: int):
    pairs = sorted((int(n.network_address), int(n.broadcast_address)) for n in networks if n.version == version)
    merged = []
    for start, end in pairs:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(a, b) for a, b in merged]

def normalize_interval_union(*groups):
    """Merge arbitrarily ordered/overlapping interval lists before set operations."""
    pairs = sorted(pair for group in groups for pair in group)
    merged = []
    for start, end in pairs:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def interval_size(values):
    return sum(end - start + 1 for start, end in values)

def intersect_one_range(start: int, end: int, values):
    """Intersect one address interval with a sorted, disjoint interval list in O(log n + k)."""
    output = []
    index = bisect_left(values, (start, -1))
    if index > 0 and values[index - 1][1] >= start:
        index -= 1
    while index < len(values) and values[index][0] <= end:
        lo = max(start, values[index][0])
        hi = min(end, values[index][1])
        if lo <= hi:
            output.append((lo, hi))
        index += 1
    return output

def subtract_one_range(start: int, end: int, masks):
    """Subtract a sorted, disjoint interval list from one range in O(log n + k)."""
    output = []
    cursor = start
    index = bisect_left(masks, (start, -1))
    if index > 0 and masks[index - 1][1] >= start:
        index -= 1
    while index < len(masks) and masks[index][0] <= end:
        lo, hi = masks[index]
        if lo > cursor:
            output.append((cursor, min(end, lo - 1)))
        cursor = max(cursor, hi + 1)
        if cursor > end:
            break
        index += 1
    if cursor <= end:
        output.append((cursor, end))
    return output

def subtract_ranges(ranges, masks):
    """Subtract a mask from a small list of intervals using indexed single-range subtraction."""
    return [piece for start, end in ranges for piece in subtract_one_range(start, end, masks)]

def intersect(a, b):
    out = []
    i = j = 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if lo <= hi:
            out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out

def subtract(a, b):
    out = []
    j = 0
    for start, end in a:
        cursor = start
        while j < len(b) and b[j][1] < cursor:
            j += 1
        k = j
        while k < len(b) and b[k][0] <= end:
            lo, hi = b[k]
            if lo > cursor:
                out.append((cursor, min(end, lo - 1)))
            cursor = max(cursor, hi + 1)
            if cursor > end:
                break
            k += 1
        if cursor <= end:
            out.append((cursor, end))
    return out

def union_networks(*groups):
    return set().union(*(set(g) for g in groups)) if groups else set()

def addr_counts(networks):
    return {f"ipv{v}": interval_size(intervals(networks, v)) for v in (4, 6)}

def networks_from_intervals(values, version: int):
    """Convert disjoint integer address intervals back to minimal CIDRs."""
    output = set()
    address_type = ipaddress.IPv4Address if version == 4 else ipaddress.IPv6Address
    for start, end in values:
        output.update(ipaddress.summarize_address_range(address_type(start), address_type(end)))
    return output

def subtract_networks(source, *masks):
    """Subtract masks by exact address space, not by CIDR-object equality."""
    output = set()
    for version in (4, 6):
        remaining = intervals(source, version)
        for mask in masks:
            remaining = subtract(remaining, intervals(mask, version))
        output.update(networks_from_intervals(remaining, version))
    return output

def potential_ipsum_direct_overlap(preblock, private, approved_blocked, ipsum):
    """Count review-only /24 address space intersecting eligible DIRECT, without summing rows."""
    result = {}
    for version in (4, 6):
        eligible = subtract(intervals(preblock, version), intervals(private, version))
        eligible = subtract(eligible, intervals(approved_blocked, version))
        review_only = subtract(intervals(ipsum, version), intervals(approved_blocked, version))
        result[version] = interval_size(intersect(eligible, review_only))
    return result

def blocked_prefix_impact(network, preblock_after_private, approved_blocked):
    """Return eligible DIRECT overlap, approved overlap within it, and incremental impact."""
    version = network.version
    start = int(network.network_address)
    end = int(network.broadcast_address)
    direct_overlap = intersect_one_range(start, end, preblock_after_private[version])
    overlap = interval_size(direct_overlap)
    already = sum(
        interval_size(intersect_one_range(lo, hi, approved_blocked[version]))
        for lo, hi in direct_overlap
    )
    return overlap, already, max(0, overlap - already)

def parse_blocked_base(path: Path):
    return parse_cidr_file(path, allow_hosts=True)[0]

def build_service_protection_masks(rir, service_sources):
    """Return literal service hosts and the full resolver-protection address space.

    Select hosts before clipping or collapsing so neither an allocation boundary
    nor a provider network can manufacture a literal service host.
    """
    ky = service_sources.get("kyoresuas-standard", set())
    hxehex = service_sources.get("hxehex-mobile-hosts", set())
    operators = service_sources.get("operator-whitelist", set())
    w1zardz = service_sources.get("w1zardz-service-direct", set())
    exact = {net for net in ky | hxehex if net.prefixlen == net.max_prefixlen}
    resolver = ky | hxehex | operators
    regional = union_networks(*(rir[country] for country in ("RU", "BY", "KZ")))
    w1zardz_hosts = {net for net in w1zardz if net.prefixlen == net.max_prefixlen}
    for version in (4, 6):
        # Do not collapse adjacent W1ZARDZ host rows into broader CIDRs.
        ru_intervals = intervals(rir["RU"], version)
        exact.update(net for net in w1zardz_hosts if net.version == version and
                     intersect_one_range(int(net.network_address), int(net.network_address), ru_intervals))
        resolver.update(networks_from_intervals(
            intersect(intervals(w1zardz, version), intervals(regional, version)), version
        ))
    return exact, set(collapse(resolver))


def class_aware_effective_block_set(
    blocked_exact: set,
    blocked_resolved: set,
    core_company_prefixes: set,
    shared_infrastructure_prefixes: set,
    regional_origin_prefixes: set | None = None,
    service_exact_hosts: set | None = None,
    service_resolver_prefixes: set | None = None,
    non_exempt: set | None = None,
):
    """Hard IP evidence wins over every origin and service protection mask."""
    if core_company_prefixes & shared_infrastructure_prefixes:
        raise ValueError("CORE_CORPORATE and SHARED_INFRA exact prefix masks overlap")
    regional = regional_origin_prefixes or set()
    service_exact = service_exact_hosts or set()
    if any(net.prefixlen != net.max_prefixlen for net in service_exact):
        raise ValueError("Hard service exceptions must be literal host prefixes")
    service_resolver = (service_resolver_prefixes or set()) | service_exact
    unconditional = non_exempt or set()
    resolved_only = subtract_networks(blocked_resolved, blocked_exact | unconditional)
    effective_exact = blocked_exact | unconditional
    effective_resolved = subtract_networks(
        resolved_only,
        core_company_prefixes | shared_infrastructure_prefixes | regional | service_resolver
    )
    return set(collapse(effective_exact | effective_resolved)), resolved_only

def parse_ipsum(path: Path):
    networks = set()
    raw = invalid = 0
    for line_no, original in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        token = line.split()[0].strip().strip('"')
        try:
            net = ipaddress.ip_network(token, strict=True)
        except ValueError:
            invalid += 1
            continue
        raw += 1
        if net.version != 4 or net.prefixlen != 24:
            raise ValueError(f"Antifilter ipsum must contain IPv4 /24 summaries only; line {line_no}: {net}")
        networks.add(net)
    if not networks:
        raise ValueError("Antifilter ipsum /24 feed is empty")
    if invalid > max(20, int((raw + invalid) * 0.001)):
        raise ValueError(f"Antifilter ipsum has too many invalid rows: {invalid}")
    return networks, {"raw_rows": raw + invalid, "valid_rows": raw, "invalid_rows": invalid}

def load_service_inputs(args, telegram=None):
    if telegram is None:
        telegram = read_telegram_feed(PINNED_FEED)
    sources = {}
    source_stats = {}
    provenance_rows = []
    ky_service_prefixes, service_rows, service_count, services_generated = parse_services_json(args.kyoresuas_services)
    if service_count < 50:
        raise ValueError(f"Kyoresuas ru-standard service catalog unexpectedly small: {service_count} services")
    sources["kyoresuas-standard"] = ky_service_prefixes
    # Preserve the publisher's aggregate IPv4/IPv6 files as a cross-check. Any
    # aggregate prefix not present in the service JSON remains attributed to the
    # same publisher/tier, rather than being dropped or misattributed.
    v4, stat4 = parse_cidr_file(args.kyoresuas_v4, allow_hosts=True)
    v6, stat6 = parse_cidr_file(args.kyoresuas_v6, allow_hosts=True)
    if any(n.version != 4 for n in v4) or any(n.version != 6 for n in v6):
        raise ValueError("Kyoresuas Standard IPv4/IPv6 feed family mismatch")
    ky_feed = v4 | v6
    unmatched = ky_feed - ky_service_prefixes
    sources["kyoresuas-standard"].update(ky_feed)
    for net in sorted(unmatched, key=lambda n:(n.version,int(n.network_address),n.prefixlen)):
        service_rows.append({
            "source_id":"kyoresuas-standard",
            "category":"aggregate-only",
            "service":"aggregate prefix not mapped in services.json",
            "tier":"standard",
            "asn_list":"",
            "domains":"0",
            "prefix":str(net),
        })
    source_stats["kyoresuas-standard"] = {
        "raw_files": [args.kyoresuas_v4.name, args.kyoresuas_v6.name, args.kyoresuas_services.name],
        "service_count": service_count,
        "services_generated_at": services_generated,
        "service_json_prefixes": len(ky_service_prefixes),
        "aggregate_feed_prefixes": len(ky_feed),
        "aggregate_only_prefixes": len(unmatched),
        "ipv4_raw_rows": stat4["raw_rows"],
        "ipv6_raw_rows": stat6["raw_rows"],
    }
    provenance_rows.extend(service_rows)

    for source_id, path in (
        ("w1zardz-service-direct", args.w1zardz),
        ("hxehex-mobile-hosts", args.hxehex_ip),
        ("operator-whitelist", args.escapingworm),
    ):
        networks, stats = parse_cidr_file(path, allow_hosts=True)
        if source_id == "hxehex-mobile-hosts":
            masks = {v: intervals(telegram, v) for v in (4, 6)}
            # Filter raw rows before host classification. Never create a literal
            # host exception by splitting a partially overlapping upstream CIDR.
            conflicts = {
                net for net in networks if intersect_one_range(
                    int(net.network_address), int(net.broadcast_address), masks[net.version]
                )
            }
            networks.difference_update(conflicts)
            stats["telegram_unique_prefixes_rejected"] = len(conflicts)
        sources[source_id] = networks
        source_stats[source_id] = {"raw_files":[path.name], **stats}
        for net in sorted(networks, key=lambda n:(n.version,int(n.network_address),n.prefixlen)):
            provenance_rows.append({
                "source_id":source_id,
                "category":"",
                "service":"",
                "tier":"",
                "asn_list":"",
                "domains":"",
                "prefix":str(net),
            })
    return sources, source_stats, provenance_rows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--hydra", type=Path, required=True)
    parser.add_argument("--rir", type=Path, required=True)
    parser.add_argument("--kyoresuas-v4", type=Path, required=True)
    parser.add_argument("--kyoresuas-v6", type=Path, required=True)
    parser.add_argument("--kyoresuas-services", type=Path, required=True)
    parser.add_argument("--w1zardz", type=Path, required=True)
    parser.add_argument("--hxehex-ip", type=Path, required=True)
    parser.add_argument("--escapingworm", type=Path, required=True)
    parser.add_argument("--blocked-base", type=Path, required=True)
    parser.add_argument("--blocked-exact", type=Path, required=True)
    parser.add_argument("--blocked-resolved", type=Path, required=True)
    parser.add_argument("--company-prefixes", type=Path, required=True)
    parser.add_argument("--core-company-prefixes", type=Path, required=True)
    parser.add_argument("--shared-infrastructure-prefixes", type=Path, required=True)
    parser.add_argument("--regional-origin-prefixes", type=Path, required=True)
    parser.add_argument("--reviewed-operator-prefixes", type=Path)
    parser.add_argument("--regional-admission-exclusions", type=Path, required=True)
    parser.add_argument("--ipsum", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--categories", type=Path, required=True)
    parser.add_argument("--quality", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--prefix-provenance", type=Path, required=True)
    parser.add_argument("--blocked-provenance", type=Path, required=True)
    parser.add_argument("--blocked-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    base_bytes = args.base.read_bytes()
    base = parse_geoip_dat(args.base)
    if set(base) != {"RU", "PRIVATE"}:
        raise ValueError(f"v37 baseline must contain exactly RU and PRIVATE; got {sorted(base)}")
    base_ru, private = set(base["RU"]), set(base["PRIVATE"])
    base_ru_iv = {v: intervals(base_ru, v) for v in (4, 6)}
    private_iv = {v: intervals(private, v) for v in (4, 6)}

    rir, rir_rows = parse_rir_tsv(args.rir)
    telegram = read_telegram_feed(PINNED_FEED)
    service_sources, source_stats, prefix_rows = load_service_inputs(args, telegram)
    hydra_sources = parse_hydra_direct_whitelist(args.hydra)
    for hydra_id, hydra_nets in hydra_sources.items():
        source_stats[hydra_id] = {"raw_files": [args.hydra.name], "valid_rows": len(hydra_nets)}
        for net in sorted(hydra_nets, key=lambda n: (n.version, int(n.network_address), n.prefixlen)):
            prefix_rows.append({"source_id": hydra_id, "category": "routing-intent",
                "service": "", "tier": "", "asn_list": "", "domains": "", "prefix": str(net)})
    service_union = union_networks(*service_sources.values())
    regional_union = union_networks(*rir.values())
    blocked_base = parse_blocked_base(args.blocked_base)
    blocked_exact = parse_blocked_base(args.blocked_exact)
    blocked_resolved = parse_blocked_base(args.blocked_resolved)
    if any(intervals(blocked_base, v) != intervals(blocked_exact | blocked_resolved, v) for v in (4, 6)):
        raise ValueError("v41 blocked union address space does not match exact plus resolver-only sidecars")

    company_prefixes, company_prefix_stats = parse_cidr_file(args.company_prefixes, allow_hosts=False)
    core_company_prefixes, core_company_stats = parse_cidr_file(args.core_company_prefixes, allow_hosts=False)
    shared_infrastructure_prefixes, shared_infrastructure_stats = parse_cidr_file(
        args.shared_infrastructure_prefixes, allow_hosts=False
    )
    if not company_prefixes:
        raise ValueError("Company ASN origin prefix set is empty; refusing to disable policy checks")
    if core_company_prefixes & shared_infrastructure_prefixes:
        raise ValueError("CORE_CORPORATE and SHARED_INFRA prefix masks must be disjoint")
    if core_company_prefixes | shared_infrastructure_prefixes != company_prefixes:
        raise ValueError("CORE/SHARED prefix masks must exactly partition the all-company prefix set")
    regional_with_companies, regional_origin_stats = parse_cidr_file(args.regional_origin_prefixes, allow_hosts=False)
    regional_only = subtract_networks(regional_with_companies, company_prefixes)
    service_exact, service_resolver = build_service_protection_masks(rir, service_sources)

    ipsum, ipsum_stats = parse_ipsum(args.ipsum)
    if len(ipsum) < 1000:
        raise ValueError(f"Antifilter ipsum review feed unexpectedly small: {len(ipsum)} /24 prefixes")

    # DNS and unverified history cannot cut any registered regional resource.
    # Explicit subnet/IP evidence and Telegram remain unconditional.
    blocked, resolved_only = class_aware_effective_block_set(
        blocked_exact, blocked_resolved, core_company_prefixes,
        shared_infrastructure_prefixes, regional_only | regional_union, service_exact, service_resolver,
        non_exempt=telegram,
    )
    ipsum_effective = subtract_networks(
        ipsum, core_company_prefixes | shared_infrastructure_prefixes | regional_only | regional_union | service_resolver
    )

    # Hydra's DIRECT and WHITELIST signal user-requested routes, not geography or
    # first-party ownership. Never include Hydra in CORE/service exemptions.
    hydra_union = union_networks(*hydra_sources.values())
    additions = regional_union | service_union | company_prefixes | regional_only | hydra_union
    source_stats["all-company-asn-origins"] = company_prefix_stats
    source_stats["core-company-asn-origins"] = core_company_stats
    source_stats["shared-infrastructure-asn-origins"] = shared_infrastructure_stats
    source_stats["rir-rukzby-selected-origin-protected"] = regional_origin_stats
    source_stats["verified-service-exact-hosts"] = {"valid_rows": len(service_exact), "invalid_rows": 0}
    source_stats["verified-service-resolver-protected"] = {"valid_rows": len(service_resolver), "invalid_rows": 0}
    for source_id, networks, category in (
        ("all-company-asn-origins", company_prefixes, "curated company ASN origin"),
        ("core-company-asn-origins", core_company_prefixes, "CORE_CORPORATE exact origin"),
        ("shared-infrastructure-asn-origins", shared_infrastructure_prefixes, "SHARED_INFRA exact origin"),
        ("rir-rukzby-selected-origin-protected", regional_only, "RIR RU+BY+KZ selected-origin resolver exception"),
        ("verified-service-exact-hosts", service_exact, "Literal service host (resolver protection only)"),
        ("verified-service-resolver-protected", service_resolver, "Verified service resolver protection"),
    ):
        for net in sorted(networks, key=lambda n: (n.version, int(n.network_address), n.prefixlen)):
            prefix_rows.append({
                "source_id": source_id,
                "category": category,
                "service": "",
                "tier": "",
                "asn_list": "",
                "domains": "",
                "prefix": str(net),
            })
    reviewed = parse_reviewed_operator_prefixes(args.reviewed_operator_prefixes) if args.reviewed_operator_prefixes else {}
    reviewed_source = "reviewed-operator-prefixes"
    if args.reviewed_operator_prefixes:
        source_stats[reviewed_source] = {
            "raw_files": [args.reviewed_operator_prefixes.name],
            "valid_rows": len(reviewed),
            "input_sha256": sha256(args.reviewed_operator_prefixes.read_bytes()),
            "protection": "none",
        }
        prefix_rows.extend(reviewed_operator_provenance(reviewed, reviewed_source))
    # Reviewed networks contribute coverage only. They do not enter any block exemption mask.
    additions.update(reviewed)
    admission_exclusions = parse_regional_admission_exclusions(args.regional_admission_exclusions)
    for row in admission_exclusions.values():
        prefix_rows.append({
            "source_id": "regional-admission-exclusion",
            "category": "Reviewed foreign assignment",
            "service": row["delegated_country"] + " -> " + row["assignment_country"],
            "tier": "", "asn_list": row["origin_asn"], "domains": "", "prefix": row["prefix"],
        })
    preblock = base_ru | additions
    preblock_iv = {v: intervals(preblock, v) for v in (4, 6)}
    core_company_iv = {v: intervals(core_company_prefixes, v) for v in (4, 6)}
    shared_infrastructure_iv = {v: intervals(shared_infrastructure_prefixes, v) for v in (4, 6)}
    regional_only_iv = {v: intervals(regional_only, v) for v in (4, 6)}
    regional_resource_iv = {v: intervals(regional_union, v) for v in (4, 6)}
    service_exact_iv = {v: intervals(service_exact, v) for v in (4, 6)}
    service_resolver_iv = {v: intervals(service_resolver, v) for v in (4, 6)}
    blocked_iv = {v: intervals(blocked, v) for v in (4, 6)}
    resolved_only_iv = {v: intervals(resolved_only, v) for v in (4, 6)}
    # CIDR set difference is not address-space subtraction: e.g. removing
    # 203.0.113.128/25 from a covering 203.0.113.0/24 must retain only the /25.
    # Convert to exact intervals before subtracting PRIVATE and RKN block prefixes.
    routing_exclusions = blocked | set(admission_exclusions)
    final = set(collapse(subtract_networks(preblock, private, routing_exclusions)))
    admission_iv = {v: intervals(admission_exclusions, v) for v in (4, 6)}
    admission_removed = {
        v: interval_size(intersect(subtract(subtract(preblock_iv[v], private_iv[v]), blocked_iv[v]), admission_iv[v]))
        for v in (4, 6)
    }
    hydra_expected = hydra_expected_after_policy(hydra_sources, private, routing_exclusions)
    if any(subtract(intervals(hydra_expected, v), intervals(final, v)) for v in (4, 6)):
        raise ValueError("Hydra DIRECT/WHITELIST coverage missing after PRIVATE/block policy")
    final_iv = {v: intervals(final, v) for v in (4, 6)}
    final_private = set(collapse(private))

    new_vs_base = {}
    for v in (4, 6):
        source_iv = intervals(additions, v)
        new_vs_base[v] = subtract(subtract(source_iv, private_iv[v]), blocked_iv[v])
        new_vs_base[v] = subtract(subtract(new_vs_base[v], admission_iv[v]), base_ru_iv[v])

    # RIR prefix attribution, including country and registry. These rows are
    # separate from service-derived source provenance and do not infer geography.
    rir_provenance = []
    for country in ("RU", "BY", "KZ"):
        for net in sorted(rir[country], key=lambda n:(n.version,int(n.network_address),n.prefixlen)):
            v = net.version
            first = int(net.network_address)
            last = int(net.broadcast_address)
            overlap_base = interval_size(intersect_one_range(first, last, base_ru_iv[v]))
            after_policy = subtract_one_range(first, last, private_iv[v])
            after_policy = subtract_ranges(subtract_ranges(after_policy, blocked_iv[v]), admission_iv[v])
            new_only = subtract_ranges(after_policy, base_ru_iv[v])
            rir_provenance.append({
                "source_id":"rir-resource-"+country,
                "country":country,
                "registry":"multiple; see resource inventory TSV",
                "prefix":str(net),
                "family":"IPv"+str(v),
                "addresses":net.num_addresses,
                "base_ru_overlap_addresses":overlap_base,
                "new_direct_addresses_after_private_rkn":interval_size(new_only),
            })
    for row in rir_provenance:
        prefix_rows.append({
            "source_id":row["source_id"],
            "category":"RIR resource registration",
            "service":row["country"],
            "tier":"",
            "asn_list":"",
            "domains":"",
            "prefix":row["prefix"],
        })

    # Source contribution: address-space union per source, not additive totals.
    metrics_rows = []
    measured_sources = [
        ("rir-RU", rir["RU"]), ("rir-BY", rir["BY"]), ("rir-KZ", rir["KZ"]),
        ("corporate-company-asn-origins", company_prefixes),
        ("rir-rukzby-selected-origin-protected", regional_only),
        ("verified-service-exact-hosts", service_exact),
        ("verified-service-resolver-protected", service_resolver),
    ]
    if args.reviewed_operator_prefixes:
        measured_sources.append((reviewed_source, reviewed))
    for source_id, networks in measured_sources + list(service_sources.items()) + list(hydra_sources.items()):
        row = {"source_id":source_id,"unique_cidrs":len(networks)}
        for v in (4, 6):
            src_iv = intervals(networks, v)
            row[f"ipv{v}_addresses"] = interval_size(src_iv)
            row[f"ipv{v}_already_in_v37"] = interval_size(intersect(src_iv, base_ru_iv[v]))
            eligible = subtract(src_iv, private_iv[v])
            eligible = subtract(subtract(eligible, blocked_iv[v]), admission_iv[v])
            row[f"ipv{v}_new_after_policy"] = interval_size(subtract(eligible, base_ru_iv[v]))
        row.update({k:str(v) for k,v in source_stats.get(source_id,{}).items() if isinstance(v,(str,int))})
        metrics_rows.append(row)

    # Compute exact v41 delta and /24 what-if analysis using the same corporate
    # exemption. Only the effective (non-corporate) blocked set is subtracted.
    delta_v4 = interval_size(new_vs_base[4])
    delta_v6 = interval_size(new_vs_base[6])
    base_blocked_iv = blocked_iv
    ipsum_overlap_direct = potential_ipsum_direct_overlap(preblock, private, blocked, ipsum_effective)
    preblock_after_private_iv = {v: subtract(preblock_iv[v], private_iv[v]) for v in (4,6)}
    exempted_blocked = subtract_networks(blocked_base, blocked)
    exempted_blocked_iv = {v: intervals(exempted_blocked, v) for v in (4,6)}
    exempted_blocked_counts = addr_counts(exempted_blocked)
    exempted_direct_counts = {
        v: interval_size(intersect(exempted_blocked_iv[v], preblock_after_private_iv[v]))
        for v in (4,6)
    }
    core_exempted_direct_counts = {
        v: interval_size(intersect(
            intersect(exempted_blocked_iv[v], core_company_iv[v]), preblock_after_private_iv[v]
        )) for v in (4,6)
    }
    shared_resolver_exempted_direct_counts = {
        v: interval_size(intersect(
            intersect(resolved_only_iv[v], shared_infrastructure_iv[v]), preblock_after_private_iv[v]
        )) for v in (4,6)
    }
    # Precompute each address-space policy mask once, outside the CIDR loop.
    # Normalizing full protection masks per blocked row caused quadratic-scale CI work.
    unblocked_direct_iv = {
        v: subtract(preblock_after_private_iv[v], base_blocked_iv[v]) for v in (4, 6)
    }
    eligible_impact_iv = {}
    for shared_allowed in (False, True):
        eligible_impact_iv[shared_allowed] = {}
        for v in (4, 6):
            protect = normalize_interval_union(
                core_company_iv[v], service_resolver_iv[v], service_exact_iv[v],
                shared_infrastructure_iv[v], regional_only_iv[v], regional_resource_iv[v],
            ) if shared_allowed else []
            eligible_impact_iv[shared_allowed][v] = subtract(unblocked_direct_iv[v], protect)

    blocked_rows = []
    for source_id, networks, shared_allowed in (
        ("v41-exact-and-legacy-hard-blocks", blocked_exact, False),
        ("v41-resolver-only-candidates", resolved_only, True),
        ("antifilter-ipsum-24-review-only", ipsum, True),
    ):
        for net in sorted(networks,key=lambda n:(n.version,int(n.network_address),n.prefixlen)):
            v=net.version
            overlap, already, potential = blocked_prefix_impact(net, preblock_after_private_iv, base_blocked_iv)
            direct_parts = intersect_one_range(int(net.network_address), int(net.broadcast_address), preblock_after_private_iv[v])
            core_exempted = interval_size(intersect(direct_parts, core_company_iv[v])) if shared_allowed else 0
            shared_exempted = interval_size(intersect(direct_parts, shared_infrastructure_iv[v])) if shared_allowed else 0
            # Compute incremental impact on address-space intervals.  Exemptions can
            # overlap each other or the already-effective blocked set; subtracting
            # raw exemption counts would double-count such intersections.
            potential = interval_size(intersect_one_range(
                int(net.network_address), int(net.broadcast_address),
                eligible_impact_iv[shared_allowed][v]
            ))
            blocked_rows.append({
                "source_id":source_id,
                "prefix":str(net),
                "family":"IPv"+str(v),
                "addresses":net.num_addresses,
                "overlap_preblock_direct":overlap,
                "already_approved_blocked":already,
                "core_company_asn_exempted_addresses":core_exempted,
                "shared_infrastructure_resolver_exempted_addresses":shared_exempted,
                "potential_additional_proxy_addresses":potential,
            })

    output_entries = {"PRIVATE":final_private,"RU":final}
    payload = encode_geoip(output_entries)
    args.output.write_bytes(payload)
    decoded = parse_geoip_dat(args.output)
    if decoded != {"PRIVATE":final_private,"RU":final}:
        raise ValueError("v41 protobuf read-back verification failed")
    if intervals(decoded["RU"],4) != final_iv[4] or intervals(decoded["RU"],6) != final_iv[6]:
        raise ValueError("v41 output address space mismatch")
    if any(intersect(intervals(decoded["RU"],v),private_iv[v]) for v in (4,6)):
        raise ValueError("PRIVATE precedence violation in v41")
    if any(intersect(intervals(decoded["RU"],v),blocked_iv[v]) for v in (4,6)):
        raise ValueError("Non-corporate RKN blocked destination remains in DIRECT v41")
    assert_regional_admission_disjoint(decoded["RU"], admission_exclusions)
    for v in (4,6):
        company_expected = normalize_interval_union(
            core_company_iv[v], shared_infrastructure_iv[v], regional_only_iv[v],
            regional_resource_iv[v], service_resolver_iv[v], service_exact_iv[v],
        )
        company_expected = subtract(subtract(company_expected, private_iv[v]), blocked_iv[v])
        company_missing = subtract(subtract(company_expected, admission_iv[v]), final_iv[v])
        if company_missing:
            raise ValueError(f"Class-aware company-ASN coverage lost in IPv{v} beyond PRIVATE/hard-block/admission precedence")

    with args.metrics.open("w",encoding="utf-8",newline="") as f:
        fields = sorted({k for row in metrics_rows for k in row})
        writer=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
        writer.writeheader()
        writer.writerows(metrics_rows)
    with args.prefix_provenance.open("w",encoding="utf-8",newline="") as f:
        fields=["source_id","category","service","tier","asn_list","domains","prefix"]
        writer=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
        writer.writeheader()
        writer.writerows(prefix_rows)
    with args.blocked_provenance.open("w",encoding="utf-8",newline="") as f:
        fields=["source_id","prefix","family","addresses","overlap_preblock_direct","already_approved_blocked","core_company_asn_exempted_addresses","shared_infrastructure_resolver_exempted_addresses","potential_additional_proxy_addresses"]
        writer=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
        writer.writeheader()
        writer.writerows(blocked_rows)
    args.blocked_output.write_text(
        "# v41 effective blocks: IP/subnet evidence and Telegram outrank all DIRECT masks.\n"
        "# DNS-derived and unverified legacy entries cannot carve protected regional or service coverage.\n"
        "# PRIVATE always wins; Antifilter ipsum /24 remains review-only.\n"
        + "".join(str(n)+"\n" for n in sorted(blocked,key=lambda n:(n.version,int(n.network_address),n.prefixlen))),
        encoding="utf-8",
    )

    base_counts = addr_counts(base_ru)
    final_counts = addr_counts(final)
    private_counts = addr_counts(private)
    args.categories.write_text(
        "# GeoIP DIRECT RU+BY+KZ v41 categories; RU is the regional/service DIRECT bucket.\n"
        + f"RU\t{len(final)}\tIPv4={final_counts['ipv4']}\tIPv6={final_counts['ipv6']}\n"
        + f"PRIVATE\t{len(final_private)}\tIPv4={private_counts['ipv4']}\tIPv6={private_counts['ipv6']}\n",
        encoding="utf-8",
    )
    blocked_counts = addr_counts(blocked)
    private_counts = addr_counts(private)
    quality = [
        "GeoIP DIRECT RU+BY+KZ CLIENT v41 — provenance-aware IP exclusions",
        "Generated UTC: "+datetime.now(timezone.utc).isoformat(),
        "Base v37 GeoIP SHA-256: "+sha256(base_bytes),
        "v41 GeoIP SHA-256: "+sha256(payload),
        "",
        "POLICY",
        "- Regional registration and service sources remain DIRECT except for explicitly reviewed admission conflicts.",
        "- Regional admission exclusions (not RKN): " + ", ".join(row["prefix"] for row in admission_exclusions.values()),
        f"- IPv4 removed by regional admission exclusions after PRIVATE and block policy: {admission_removed[4]}",
        "- PRIVATE has absolute precedence.",
        "- CORE_CORPORATE exact origin prefixes are protected from the resolver layer only.",
        "- SHARED_INFRA exact origin prefixes are protected only against the resolver-only layer.",
        "- Official Telegram CIDRs are non-exempt in DIRECT. Overlapping HXEHEX entries are rejected before service protection.",
        "- Current ip.lst and ipresolve.lst are DNS-derived; unverified historical v38 is advisory.",
        "- Current bounded subnet feed and reviewed direct registry IP/subnet records remain hard.",
        "- MOAS is CORE_CORPORATE when any exact origin is CORE; otherwise SHARED_INFRA receives resolver-only protection.",
        "- RIR RU+BY+KZ selected origins and registered resources protect against the resolver layer, not hard blocks.",
        "- Regional registration alone does not imply corporate ownership.",
        "- No origin, literal service host or operator whitelist may override hard IP/subnet evidence.",
        "- PRIVATE has absolute precedence over every origin class and all block exceptions.",
        "- IP GeoIP cannot distinguish unrelated tenants on shared IPs; broad RKN summaries can overblock co-resident services.",
        "",
        "BASELINE V37",
        f"RU CIDRs: {len(base_ru)}",
        f"RU IPv4 addresses: {base_counts['ipv4']}",
        f"RU IPv6 addresses: {base_counts['ipv6']}",
        "",
        "V41 FINAL",
        f"RU CIDRs: {len(final)}",
        f"RU IPv4 addresses: {final_counts['ipv4']}",
        f"RU IPv6 addresses: {final_counts['ipv6']}",
        f"New IPv4 addresses vs v37 after PRIVATE/RKN/company-ASN exception: {delta_v4}",
        f"New IPv6 addresses vs v37 after PRIVATE/RKN/company-ASN exception: {delta_v6}",
        f"PRIVATE IPv4 addresses: {private_counts['ipv4']}",
        f"PRIVATE IPv6 addresses: {private_counts['ipv6']}",
        "",
        "RIR RESOURCE INVENTORY",
        f"RU resource CIDRs: {len(rir['RU'])}",
        f"BY resource CIDRs: {len(rir['BY'])}",
        f"KZ resource CIDRs: {len(rir['KZ'])}",
        f"RIR rows with registry/status provenance: {rir_rows}",
        "RIR registration is resource-holder evidence, not physical geolocation or proof of current BGP reachability.",
        "",
        "HYDRA ROUTING-INTENT COVERAGE",
        f"Hydra DIRECT CIDRs: {len(hydra_sources['hydra-direct'])}",
        f"Hydra WHITELIST CIDRs: {len(hydra_sources['hydra-whitelist'])}",
        f"Hydra eligible after PRIVATE and v41 blocks: {addr_counts(hydra_expected)}",
        "Hydra is routing-intent, not a geolocation or corporate attribution; it does not override blocked/PRIVATE.",
        "",
        "SERVICE DIRECT INPUTS",
        f"Kyoresuas Standard services represented in service catalog: {service_stats_count(source_stats)}",
        f"W1ZARDZ unique service/direct prefixes: {len(service_sources['w1zardz-service-direct'])}",
        f"HXEHEX exact host-IP prefixes: {len(service_sources['hxehex-mobile-hosts'])}",
        f"Escapingworm operator whitelist prefixes: {len(service_sources['operator-whitelist'])}",
        f"Literal service hosts (resolver protection only): {len(service_exact)}",
        f"Service resolver-protected address space: {addr_counts(service_resolver)}",
        "Service and operator whitelist routes are separate from geographic/RIR resource evidence.",
        "Service datasets can include foreign-located or shared-provider endpoints; no country geolocation filter was applied.",
        "",
        "RKN BLOCKS AND CORPORATE COMPANY-ASN EXCEPTION",
        f"Original v37 approved blocked CIDRs: {len(blocked_base)}",
        f"Effective v41 blocked CIDRs after class-aware exceptions: {len(blocked)}",
        f"Total block addresses exempted: IPv4={exempted_blocked_counts['ipv4']} IPv6={exempted_blocked_counts['ipv6']}",
        f"Total exempted addresses intersecting DIRECT after PRIVATE: IPv4={exempted_direct_counts[4]} IPv6={exempted_direct_counts[6]}",
        f"CORE_CORPORATE exempted DIRECT addresses after PRIVATE: IPv4={core_exempted_direct_counts[4]} IPv6={core_exempted_direct_counts[6]}",
        f"SHARED_INFRA resolver-only exempted DIRECT addresses: IPv4={shared_resolver_exempted_direct_counts[4]} IPv6={shared_resolver_exempted_direct_counts[6]}",
        f"All company origin prefixes: {len(company_prefixes)}; IPv4 addresses={addr_counts(company_prefixes)['ipv4']}; IPv6 addresses={addr_counts(company_prefixes)['ipv6']}",
        f"CORE_CORPORATE origin prefixes: {len(core_company_prefixes)}; SHARED_INFRA origin prefixes: {len(shared_infrastructure_prefixes)}",
        f"Antifilter ipsum REVIEW-ONLY IPv4 /24 prefixes: {len(ipsum)}",
        f"Antifilter ipsum raw/valid/invalid rows: {ipsum_stats['raw_rows']}/{ipsum_stats['valid_rows']}/{ipsum_stats['invalid_rows']}",
        f"Potential additional IPv4 DIRECT address space affected by /24 review candidates: {ipsum_overlap_direct[4]}",
        f"Potential additional IPv6 DIRECT address space affected by /24 review candidates: {ipsum_overlap_direct[6]}",
        "ipsum /24 candidates remain review-only. DNS-derived and unverified historical evidence cannot carve selected origin or RIR-resource coverage. Explicit IP/subnet evidence and Telegram take precedence.",
        "The /24 impact estimate excludes the exact corporate company-ASN prefix space exempted by the v41 policy.",
        f"Combined v41 effective blocked IPv4 address space: {blocked_counts['ipv4']}",
        f"Combined v41 effective blocked IPv6 address space: {blocked_counts['ipv6']}",
        "ipsum is a third-party RKN-derived /24 summary, not a direct official RKN API.",
        "Every /24 carve affects the whole 256-address block; on shared hosting/CDNs it may send unrelated co-resident destinations through VPN.",
        "",
        "FILES",
        "- geoip_RU.dat: final v41 GeoIP protobuf with RU and PRIVATE categories only.",
        "- geoip_RU_v41_source_metrics.tsv: per-source unique CIDR and address-space contribution; rows overlap and must not be summed.",
        "- geoip_RU_v41_prefix_provenance.tsv: service, resource and corporate-origin prefix provenance.",
        "- geoip_RU_v41_blocked_provenance.tsv: original block overlaps, corporate exemptions and review-only /24 impact estimate.",
        "- geoip_RU_v41_blocked_ip_exclusions.txt: effective non-corporate blocked set applied to v41.",
        "- geoip_RU_company_asn_bgp_prefixes.txt: exact prefixes originated by the curated corporate company-ASN allowlist.",
        "",
        "SHA-256 output: "+sha256(payload),
    ]
    args.quality.write_text("\n".join(quality)+"\n",encoding="utf-8")
    manifest = {
        "schema":2,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "base_v37_sha256":sha256(base_bytes),
        "output_sha256":sha256(payload),
        "output_bytes":len(payload),
        "sources":SOURCE_REFS,
        "telegram_official": {"cidrs": len(telegram), "input_sha256": sha256(PINNED_FEED.read_bytes())},
        "rir_inventory":{"rows":rir_rows,"countries":{c:len(rir[c]) for c in ("RU","BY","KZ")}},
        "regional_admission_exclusions": {
            "records": list(admission_exclusions.values()),
            "removed_after_block_policy": {f"ipv{v}": count for v, count in admission_removed.items()},
        },
        "service_sources":source_stats,
        "hydra_routing_intent": {
            "direct_cidrs": len(hydra_sources["hydra-direct"]),
            "whitelist_cidrs": len(hydra_sources["hydra-whitelist"]),
            "combined_eligible_address_space": addr_counts(hydra_expected),
            "precedence": "PRIVATE > effective v41 blocked set > Hydra DIRECT/WHITELIST",
            "input_sha256": sha256(args.hydra.read_bytes()),
        },
        "corporate_company_asn_prefixes":{
            "unique_prefixes":len(company_prefixes),
            "address_space":addr_counts(company_prefixes),
            "raw_valid_invalid_rows":company_prefix_stats,
            "input_sha256":sha256(args.company_prefixes.read_bytes()),
        },
        "corporate_core_prefixes":{
            "unique_prefixes":len(core_company_prefixes),
            "address_space":addr_counts(core_company_prefixes),
            "raw_valid_invalid_rows":core_company_stats,
            "input_sha256":sha256(args.core_company_prefixes.read_bytes()),
        },
        "regional_origin_prefixes":{
            "unique_prefixes":len(regional_only),
            "selected_origin_input_sha256":sha256(args.regional_origin_prefixes.read_bytes()),
            "protection":"resolver_only",
        },
        "ru_verified_service_prefixes":{
            "unique_prefixes":len(service_resolver),
            "address_space":addr_counts(service_resolver),
            "exact_host_prefixes":len(service_exact),
            "exact_host_address_space":addr_counts(service_exact),
            "resolver_protected_prefixes":len(service_resolver),
            "resolver_protected_address_space":addr_counts(service_resolver),
            "protection":"resolver_only_no_hard_override",
        },
        "shared_infrastructure_prefixes":{
            "unique_prefixes":len(shared_infrastructure_prefixes),
            "address_space":addr_counts(shared_infrastructure_prefixes),
            "raw_valid_invalid_rows":shared_infrastructure_stats,
            "input_sha256":sha256(args.shared_infrastructure_prefixes.read_bytes()),
        },
        "blocked":{
            "approved_union_original_unique":len(blocked_base),
            "exact_and_legacy_hard_unique":len(blocked_exact),
            "resolver_only_unique":len(resolved_only),
            "v41_effective_after_class_aware_exceptions_unique":len(blocked),
            "all_exempted_unique":len(exempted_blocked),
            "all_exempted_address_space":exempted_blocked_counts,
            "all_exempted_direct_after_private":{f"ipv{v}":exempted_direct_counts[v] for v in (4,6)},
            "core_company_asn_exempted_direct_after_private":{f"ipv{v}":core_exempted_direct_counts[v] for v in (4,6)},
            "shared_infrastructure_resolver_exempted_direct_after_private":{f"ipv{v}":shared_resolver_exempted_direct_counts[v] for v in (4,6)},
            "ipsum_review_only_unique":len(ipsum),
            "ipsum_company_adjusted_review_only_unique":len(ipsum_effective),
            "ipsum_auto_carved":False,
            "ipsum_sha256":sha256(args.ipsum.read_bytes()),
            "potential_additional_proxy_ipv4_addresses":ipsum_overlap_direct[4],
            "potential_additional_proxy_ipv6_addresses":ipsum_overlap_direct[6],
        },
        "base_v37_address_space":base_counts,
        "final_v41_address_space":final_counts,
        "new_after_policy":{"ipv4":delta_v4,"ipv6":delta_v6},
        "safety":{
            "this_builder_modifies_production_main":False,
            "this_builder_publishes_release":False,
            "release_workflow_is_main_only":True,
            "geolocation_used_as_admission_gate":False,
            "private_precedence_applied":True,
            "rkn_exact_ip_and_subnet_blocks_apply_to_shared_infrastructure":True,
            "confirmed_ip_subnet_precedes_all_direct_exceptions":True,
            "official_telegram_precedes_all_direct_exceptions":True,
            "shared_infrastructure_prefixes_exempt_from_resolver_layer_only":True,
            "legacy_v38_reclassification_preserves_approved_union":True,
            "rir_rukzby_selected_origin_resolver_protected":True,
            "all_direct_protection_masks_are_resolver_only":True,
            "private_precedence_over_all_exceptions":True,
            "ipsum_24_auto_carved":False,
            "hydra_direct_whitelist_added_without_block_exemption":True,
            "candidate_status":"REVIEW",
        },
        "input_sha256":{
            "base_v37_geoip":sha256(args.base.read_bytes()),
            "hydra_geoip":sha256(args.hydra.read_bytes()),
            "regional_rir_inventory":sha256(args.rir.read_bytes()),
            "regional_admission_exclusions":sha256(args.regional_admission_exclusions.read_bytes()),
            "kyoresuas_standard_ipv4":sha256(args.kyoresuas_v4.read_bytes()),
            "kyoresuas_standard_ipv6":sha256(args.kyoresuas_v6.read_bytes()),
            "kyoresuas_services_json":sha256(args.kyoresuas_services.read_bytes()),
            "w1zardz_direct":sha256(args.w1zardz.read_bytes()),
            "hxehex_ipwhitelist":sha256(args.hxehex_ip.read_bytes()),
            "escapingworm_operator_whitelist":sha256(args.escapingworm.read_bytes()),
            "v37_blocked_base":sha256(args.blocked_base.read_bytes()),
            "corporate_company_asn_origin_prefixes":sha256(args.company_prefixes.read_bytes()),
            "corporate_core_prefixes":sha256(args.core_company_prefixes.read_bytes()),
            "shared_infrastructure_prefixes":sha256(args.shared_infrastructure_prefixes.read_bytes()),
            "regional_origin_prefixes":sha256(args.regional_origin_prefixes.read_bytes()),
            "blocked_exact_and_legacy":sha256(args.blocked_exact.read_bytes()),
            "blocked_resolver_only":sha256(args.blocked_resolved.read_bytes()),
            "antifilter_ipsum":sha256(args.ipsum.read_bytes()),
        },
    }
    args.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"v41 protobuf bytes: {len(payload)} sha256={sha256(payload)}")
    print(f"v41 final RU CIDRs: {len(final)} IPv4={final_counts['ipv4']} IPv6={final_counts['ipv6']}")
    print(f"New after policy IPv4={delta_v4} IPv6={delta_v6}")
    print(f"Company prefixes={len(company_prefixes)} core={len(core_company_prefixes)} shared={len(shared_infrastructure_prefixes)}")
    print(f"Exempted DIRECT IPv4={exempted_direct_counts[4]} IPv6={exempted_direct_counts[6]}; shared resolver DIRECT IPv4={shared_resolver_exempted_direct_counts[4]}")
    print(f"RIR RU/BY/KZ rows={rir_rows}; ipsum /24 review-only={len(ipsum)}")
    return 0

def service_stats_count(stats):
    return int(stats.get("kyoresuas-standard",{}).get("service_count",0))

if __name__ == "__main__":
    raise SystemExit(main())
