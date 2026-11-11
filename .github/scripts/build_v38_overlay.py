#!/usr/bin/env python3
"""Assemble the v38 unified DIRECT RU+BY+KZ GeoIP overlay.

The v37 builder remains the trusted geographic/ASN baseline. v38 adds:
- all RU/BY/KZ registered address resources from the five RIR delegated snapshots;
- named service DIRECT destinations from pinned service-routing sources;
- a separate RKN-derived /24 blocked-destination summary.
All additions are evaluated without a geolocation gate. PRIVATE and RKN blocks always
win. The client output remains exactly two GeoIP categories: RU and PRIVATE.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SOURCE_REFS = {
    "kyoresuas-standard": {
        "repository": "kyoresuas/ru-direct",
        "commit": "0781793a159f9a53c5e68da2f46b0a64855f8cb6",
        "files": ["ru-standard.ipv4.txt", "ru-standard.ipv6.txt", "services.json"],
        "license": "MIT (repository); preserve upstream country-zone and database attributions",
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
        return ipaddress.ip_network(token, strict=False)
    address = ipaddress.ip_address(token)
    return ipaddress.ip_network((address, address.max_prefixlen if host_to_32 else address.max_prefixlen), strict=False)

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
        for token in values:
            try:
                found = parse_network(token, allow_hosts)
                break
            except ValueError:
                continue
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
    if service_count < 50 or not networks:
        raise ValueError(f"Kyoresuas service catalog unexpectedly small: {service_count} services")
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
        for en, ew, ev in protobuf_fields(entry):
            if en == 1 and ew == 2:
                category = ev.decode("ascii").upper()
            elif en == 2 and ew == 2:
                address = prefix = None
                for cn, cw, cv in protobuf_fields(ev):
                    if cn == 1 and cw == 2:
                        address = cv
                    elif cn == 2 and cw == 0:
                        prefix = int(cv)
                if address is not None and prefix is not None:
                    ip = ipaddress.ip_address(address)
                    networks.add(ipaddress.ip_network((ip, prefix), strict=False))
        if category:
            result.setdefault(category, set()).update(networks)
    if not result:
        raise ValueError("base GeoIP protobuf has no categories")
    return result

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

def interval_size(values):
    return sum(end - start + 1 for start, end in values)

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

def parse_blocked_base(path: Path):
    return parse_cidr_file(path, allow_hosts=True)[0]

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
    if len(networks) < 1000:
        raise ValueError(f"Antifilter ipsum /24 feed unexpectedly small: {len(networks)} prefixes")
    if invalid > max(20, int((raw + invalid) * 0.001)):
        raise ValueError(f"Antifilter ipsum has too many invalid rows: {invalid}")
    return networks, {"raw_rows": raw + invalid, "valid_rows": raw, "invalid_rows": invalid}

def load_service_inputs(args):
    sources = {}
    source_stats = {}
    provenance_rows = []
    ky_service_prefixes, service_rows, service_count, services_generated = parse_services_json(args.kyoresuas_services)
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
    parser.add_argument("--rir", type=Path, required=True)
    parser.add_argument("--kyoresuas-v4", type=Path, required=True)
    parser.add_argument("--kyoresuas-v6", type=Path, required=True)
    parser.add_argument("--kyoresuas-services", type=Path, required=True)
    parser.add_argument("--w1zardz", type=Path, required=True)
    parser.add_argument("--hxehex-ip", type=Path, required=True)
    parser.add_argument("--escapingworm", type=Path, required=True)
    parser.add_argument("--blocked-base", type=Path, required=True)
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
    service_sources, source_stats, prefix_rows = load_service_inputs(args)
    service_union = union_networks(*service_sources.values())
    regional_union = union_networks(*rir.values())
    blocked_base = parse_blocked_base(args.blocked_base)
    ipsum, ipsum_stats = parse_ipsum(args.ipsum)
    blocked = blocked_base | ipsum

    additions = regional_union | service_union
    preblock = base_ru | additions
    preblock_iv = {v: intervals(preblock, v) for v in (4, 6)}
    blocked_iv = {v: intervals(blocked, v) for v in (4, 6)}
    private_overlap = {v: interval_size(intersect(intervals(additions, v), private_iv[v])) for v in (4, 6)}
    block_overlap = {v: interval_size(intersect(preblock_iv[v], blocked_iv[v])) for v in (4, 6)}
    # CIDR set difference is not address-space subtraction: e.g. removing
    # 203.0.113.128/25 from a covering 203.0.113.0/24 must retain only the /25.
    # Convert to exact intervals before subtracting PRIVATE and RKN block prefixes.
    final = subtract_networks(preblock, private, blocked)
    final = set(collapse(final))
    final_iv = {v: intervals(final, v) for v in (4, 6)}
    final_private = set(collapse(private))

    new_vs_base = {}
    for v in (4, 6):
        source_iv = intervals(additions, v)
        new_vs_base[v] = subtract(subtract(source_iv, private_iv[v]), blocked_iv[v])
        new_vs_base[v] = subtract(new_vs_base[v], base_ru_iv[v])

    # RIR prefix attribution, including country and registry. These rows are
    # separate from service-derived source provenance and do not infer geography.
    rir_provenance = []
    for country in ("RU", "BY", "KZ"):
        for net in sorted(rir[country], key=lambda n:(n.version,int(n.network_address),n.prefixlen)):
            v = net.version
            overlap_base = interval_size(intersect([(int(net.network_address),int(net.broadcast_address))], base_ru_iv[v]))
            after_policy = subtract([(int(net.network_address),int(net.broadcast_address))], private_iv[v])
            after_policy = subtract(after_policy, blocked_iv[v])
            new_only = subtract(after_policy, base_ru_iv[v])
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
    for source_id, networks in [("rir-RU",rir["RU"]),("rir-BY",rir["BY"]),("rir-KZ",rir["KZ"])] + list(service_sources.items()):
        row = {"source_id":source_id,"unique_cidrs":len(networks)}
        for v in (4, 6):
            src_iv = intervals(networks, v)
            row[f"ipv{v}_addresses"] = interval_size(src_iv)
            row[f"ipv{v}_already_in_v37"] = interval_size(intersect(src_iv, base_ru_iv[v]))
            eligible = subtract(src_iv, private_iv[v])
            eligible = subtract(eligible, blocked_iv[v])
            row[f"ipv{v}_new_after_policy"] = interval_size(subtract(eligible, base_ru_iv[v]))
        row.update({k:str(v) for k,v in source_stats.get(source_id,{}).items() if isinstance(v,(str,int))})
        metrics_rows.append(row)

    # Compute unique v38 delta and the incremental blocking effect of ipsum.
    delta_v4 = interval_size(new_vs_base[4])
    delta_v6 = interval_size(new_vs_base[6])
    base_blocked_iv = {v: intervals(blocked_base, v) for v in (4,6)}
    ipsum_iv = {v: intervals(ipsum, v) for v in (4,6)}
    # Count only block space not already covered by the v37 approved set,
    # including containment by a broader v37 CIDR (not just exact CIDR equality).
    ipsum_only_iv = {
        v: subtract(ipsum_iv[v], base_blocked_iv[v]) for v in (4,6)
    }
    ipsum_overlap_direct = {
        v: interval_size(intersect(preblock_iv[v], ipsum_only_iv[v])) for v in (4,6)
    }
    blocked_rows = []
    for source_id, networks in (("v37-approved-rkn",blocked_base),("antifilter-ipsum-24",ipsum)):
        for net in sorted(networks,key=lambda n:(n.version,int(n.network_address),n.prefixlen)):
            v=net.version
            one_prefix = [(int(net.network_address),int(net.broadcast_address))]
            direct_overlap = intersect(one_prefix, preblock_iv[v])
            overlap = interval_size(direct_overlap)
            already = interval_size(intersect(direct_overlap, base_blocked_iv[v]))
            blocked_rows.append({
                "source_id":source_id,
                "prefix":str(net),
                "family":"IPv"+str(v),
                "addresses":net.num_addresses,
                "overlap_preblock_direct":overlap,
                "already_approved_blocked":already,
                "newly_carved_direct_addresses":max(0,overlap-already),
            })

    output_entries = {"PRIVATE":final_private,"RU":final}
    payload = encode_geoip(output_entries)
    args.output.write_bytes(payload)
    decoded = parse_geoip_dat(args.output)
    if decoded != {"PRIVATE":final_private,"RU":final}:
        raise ValueError("v38 protobuf read-back verification failed")
    if intervals(decoded["RU"],4) != final_iv[4] or intervals(decoded["RU"],6) != final_iv[6]:
        raise ValueError("v38 output address space mismatch")
    if any(intersect(intervals(decoded["RU"],v),private_iv[v]) for v in (4,6)):
        raise ValueError("PRIVATE precedence violation in v38")
    if any(intersect(intervals(decoded["RU"],v),blocked_iv[v]) for v in (4,6)):
        raise ValueError("RKN blocked destination remains in DIRECT v38")

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
        fields=["source_id","prefix","family","addresses","overlap_preblock_direct","already_approved_blocked","newly_carved_direct_addresses"]
        writer=csv.DictWriter(f,fieldnames=fields,delimiter="\t",lineterminator="\n")
        writer.writeheader()
        writer.writerows(blocked_rows)
    args.blocked_output.write_text(
        "# v38 approved blocked destinations: v37 conservative set plus Antifilter ipsum /24 summary.\n"
        + "".join(str(n)+"\n" for n in sorted(blocked,key=lambda n:(n.version,int(n.network_address),n.prefixlen))),
        encoding="utf-8",
    )

    base_counts = addr_counts(base_ru)
    final_counts = addr_counts(final)
    private_counts = addr_counts(private)
    args.categories.write_text(
        "# GeoIP DIRECT RU+BY+KZ v38 categories; RU is the regional/service DIRECT bucket.\n"
        + f"RU\t{len(final)}\tIPv4={final_counts['ipv4']}\tIPv6={final_counts['ipv6']}\n"
        + f"PRIVATE\t{len(final_private)}\tIPv4={private_counts['ipv4']}\tIPv6={private_counts['ipv6']}\n",
        encoding="utf-8",
    )
    blocked_counts = addr_counts(blocked)
    private_counts = addr_counts(private)
    quality = [
        "GeoIP DIRECT RU+BY+KZ CLIENT v38 — non-geographic regional/service DIRECT; RKN-only PROXY carve-outs",
        "Generated UTC: "+datetime.now(timezone.utc).isoformat(),
        "Base v37 GeoIP SHA-256: "+sha256(base_bytes),
        "v38 GeoIP SHA-256: "+sha256(payload),
        "",
        "POLICY",
        "- RU+BY+KZ registered resource prefixes and named service destinations are DIRECT regardless of geolocation.",
        "- PRIVATE has absolute precedence.",
        "- RKN-derived blocked destinations are carved from DIRECT; the output is not a geolocation whitelist.",
        "- IP GeoIP cannot distinguish unrelated tenants on shared IPs; broad RKN summaries can overblock co-resident services.",
        "",
        "BASELINE V37",
        f"RU CIDRs: {len(base_ru)}",
        f"RU IPv4 addresses: {base_counts['ipv4']}",
        f"RU IPv6 addresses: {base_counts['ipv6']}",
        "",
        "V38 FINAL",
        f"RU CIDRs: {len(final)}",
        f"RU IPv4 addresses: {final_counts['ipv4']}",
        f"RU IPv6 addresses: {final_counts['ipv6']}",
        f"New IPv4 addresses vs v37 after PRIVATE/RKN: {delta_v4}",
        f"New IPv6 addresses vs v37 after PRIVATE/RKN: {delta_v6}",
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
        "SERVICE DIRECT INPUTS",
        f"Kyoresuas Standard services represented in service catalog: {service_stats_count(source_stats)}",
        f"W1ZARDZ unique service/direct prefixes: {len(service_sources['w1zardz-service-direct'])}",
        f"HXEHEX exact host-IP prefixes: {len(service_sources['hxehex-mobile-hosts'])}",
        f"Escapingworm operator whitelist prefixes: {len(service_sources['operator-whitelist'])}",
        "Service and operator whitelist routes are separate from geographic/RIR resource evidence.",
        "Service datasets can include foreign-located or shared-provider endpoints; no country geolocation filter was applied.",
        "",
        "RKN BLOCKS",
        f"v37 approved blocked CIDRs: {len(blocked_base)}",
        f"Antifilter ipsum unique IPv4 /24 prefixes: {len(ipsum)}",
        f"Antifilter ipsum raw/valid/invalid rows: {ipsum_stats['raw_rows']}/{ipsum_stats['valid_rows']}/{ipsum_stats['invalid_rows']}",
        f"Antifilter ipsum new IPv4 addresses intersecting preblock DIRECT: {ipsum_overlap_direct[4]}",
        f"Antifilter ipsum new IPv6 addresses intersecting preblock DIRECT: {ipsum_overlap_direct[6]}",
        f"Combined v38 blocked IPv4 address space: {blocked_counts['ipv4']}",
        f"Combined v38 blocked IPv6 address space: {blocked_counts['ipv6']}",
        "ipsum is a third-party RKN-derived /24 summary, not a direct official RKN API.",
        "Every /24 carve affects the whole 256-address block; on shared hosting/CDNs it may send unrelated co-resident destinations through VPN.",
        "",
        "FILES",
        "- geoip_RU.dat: final v38 GeoIP protobuf with RU and PRIVATE categories only.",
        "- geoip_RU_v38_source_metrics.tsv: per-source unique CIDR and address-space contribution; rows overlap and must not be summed.",
        "- geoip_RU_v38_prefix_provenance.tsv: service and resource prefix provenance.",
        "- geoip_RU_v38_blocked_provenance.tsv: source-level blocked prefix and DIRECT overlap.",
        "- geoip_RU_v38_blocked_ip_exclusions.txt: exact combined blocked set applied to v38.",
        "",
        "SHA-256 output: "+sha256(payload),
    ]
    args.quality.write_text("\n".join(quality)+"\n",encoding="utf-8")
    manifest = {
        "schema":1,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "base_v37_sha256":sha256(base_bytes),
        "output_sha256":sha256(payload),
        "output_bytes":len(payload),
        "sources":SOURCE_REFS,
        "rir_inventory":{"rows":rir_rows,"countries":{c:len(rir[c]) for c in ("RU","BY","KZ")}},
        "service_sources":source_stats,
        "blocked":{"v37_unique":len(blocked_base),"ipsum_unique":len(ipsum),"ipsum_sha256":sha256(args.ipsum.read_bytes())},
        "base_v37_address_space":base_counts,
        "final_v38_address_space":final_counts,
        "new_after_policy":{"ipv4":delta_v4,"ipv6":delta_v6},
        "safety":{
            "this_builder_modifies_production_main":False,
            "this_builder_publishes_release":False,
            "release_workflow_is_main_only":True,
            "geolocation_used_as_admission_gate":False,
            "private_precedence_applied":True,
            "rkn_blocklist_applied":True,
            "candidate_status":"REVIEW",
        },
        "input_sha256":{
            "base_v37_geoip":sha256(args.base.read_bytes()),
            "regional_rir_inventory":sha256(args.rir.read_bytes()),
            "kyoresuas_standard_ipv4":sha256(args.kyoresuas_v4.read_bytes()),
            "kyoresuas_standard_ipv6":sha256(args.kyoresuas_v6.read_bytes()),
            "kyoresuas_services_json":sha256(args.kyoresuas_services.read_bytes()),
            "w1zardz_direct":sha256(args.w1zardz.read_bytes()),
            "hxehex_ipwhitelist":sha256(args.hxehex_ip.read_bytes()),
            "escapingworm_operator_whitelist":sha256(args.escapingworm.read_bytes()),
            "v37_blocked_base":sha256(args.blocked_base.read_bytes()),
            "antifilter_ipsum":sha256(args.ipsum.read_bytes()),
        },
    }
    args.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"v38 protobuf bytes: {len(payload)} sha256={sha256(payload)}")
    print(f"v38 final RU CIDRs: {len(final)} IPv4={final_counts['ipv4']} IPv6={final_counts['ipv6']}")
    print(f"New after policy IPv4={delta_v4} IPv6={delta_v6}")
    print(f"RIR RU/BY/KZ rows={rir_rows}; ipsum /24={len(ipsum)}")
    return 0

def service_stats_count(stats):
    return int(stats.get("kyoresuas-standard",{}).get("service_count",0))

if __name__ == "__main__":
    raise SystemExit(main())
