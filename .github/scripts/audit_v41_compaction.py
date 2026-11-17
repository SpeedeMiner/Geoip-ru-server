#!/usr/bin/env python3
"""Read-only v41 IPv4 compaction audit for a pinned release and restored inputs."""

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from contextlib import redirect_stdout
import csv
from hashlib import sha256
import ipaddress
import json
from pathlib import Path
import re
import sys
import tarfile

import audit_v41_asn_regressions as origins
import build_v41_overlay as overlay
from audit_v41_direct_provenance import load_snapshot, split_evidence
from build_company_asn_prefix_classes_v41 import read_company_registry, read_policy
from validate_v41_telegram import read_telegram_feed


COUNTRIES = {"RU", "BY", "KZ"}
REGIONAL = "geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt"
HARD = "geoip_RU_blocked_ip_exact_and_legacy_hard.txt"
EFFECTIVE = "geoip_RU_v41_blocked_ip_exclusions.txt"
DATA = Path(__file__).resolve().parents[1] / "data"
ASN_MEMBER = re.compile(r"(?:[^/]+/)?as/([1-9][0-9]*)/aggregated\.json")


def bounds(net):
    return int(net.network_address), int(net.broadcast_address)


def within(net, ranges):
    return overlay.intersect_one_range(*bounds(net), ranges)


def v4_networks(path):
    with path.open(encoding="utf-8") as src:
        for line in src:
            value = line.partition("#")[0].strip()
            if value and ":" not in value:
                yield ipaddress.IPv4Network(value)


def tsv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        yield from csv.DictReader(stream, delimiter="\t")


def delegated_asns(root):
    result = defaultdict(set)
    for path in sorted(root.glob("delegated-*")):
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                fields = line.rstrip().split("|")
                if (len(fields) >= 7 and fields[1] in COUNTRIES and fields[2] == "asn"
                        and fields[6] in {"allocated", "assigned", "legacy"}):
                    first, count = map(int, fields[3:5])
                    for number in range(first, first + count):
                        result[number].add(fields[1])
    if not result:
        raise ValueError("no regional RIR ASN records in restored inputs")
    return result


def fragment_blocks(direct):
    """Enumerate ancestors of existing CIDRs, never individual IPv4 addresses."""
    blocks = defaultdict(list)
    for net in overlay.collapse(direct):
        if net.version != 4:
            continue
        for size in range(20, min(23, net.prefixlen - 1) + 1):
            blocks[net.supernet(new_prefix=size)].append(net)
    return {net: parts for net, parts in blocks.items()
            if len(parts) >= 6 and 4 * sum(n.num_addresses for n in parts) >= 3 * net.num_addresses}


def observations(archive, regional, company, blocks):
    """Read aggregated per-AS members one at a time, index foreign routes only at target blocks."""
    windows = defaultdict(list)
    for block in blocks:
        windows[int(block.network_address) >> 12].append(block)
    keys = sorted(windows)
    by_block, by_origin, info = defaultdict(list), defaultdict(set), {}
    with tarfile.open(archive, "r|gz") as tar:
        for member in tar:
            match = ASN_MEMBER.fullmatch(member.name)
            if not match:
                continue
            asn = int(match[1])
            if not member.isfile() or not 0 < member.size <= 16 * 1024 * 1024:
                raise ValueError(f"invalid ASN member: {member.name}")
            with tar.extractfile(member) as stream:
                obj = json.load(stream)
            if obj.get("asn") != asn:
                raise ValueError(f"wrong ASN in {member.name}")
            metadata = obj.get("metadata") or {}
            country = str(metadata.get("countryCode") or "").upper()
            if asn in regional or asn in company or country in COUNTRIES:
                info[asn] = {"country": country, "rir_countries": sorted(regional.get(asn, ())),
                             "holder": metadata.get("description"), "handle": metadata.get("handle")}
            for value in (obj.get("prefixes") or {}).get("ipv4", []):
                _, net = origins.classify_prefix(value, 4)
                if net is None:
                    continue
                if asn in info:
                    by_origin[asn].add(net)
                lo, hi = bounds(net)
                if net.prefixlen >= 20:
                    candidates = windows.get(lo >> 12, ())
                else:
                    candidates = (block for key in keys[bisect_left(keys, lo >> 12):bisect_left(keys, (hi >> 12) + 1)]
                                  for block in windows[key])
                for block in candidates:
                    if block.overlaps(net):
                        by_block[block].append((asn, net))
    return by_origin, by_block, info


def single_origin(block, direct, observed):
    """Use most-specific observed routes; equally specific competing ASNs are ambiguous."""
    layers = defaultdict(list)
    for asn, route in observed:
        lo, hi = bounds(route)
        layers[(route.prefixlen, asn)].append((lo, hi))
    if not layers:
        return None, []
    owner = set()
    unknown = []
    for lo, hi, labels in split_evidence([bounds(block)], layers):
        if not labels:
            if overlay.intersect_one_range(lo, hi, direct):
                return None, []
            unknown.append((lo, hi))
            continue
        most_specific = max(p[0] for p in labels)
        owner.update(asn for length, asn in labels if length == most_specific)
        if len(owner) > 1:
            return None, []
    return (next(iter(owner)), unknown) if owner else (None, [])


def classify_gaps(block, direct, masks):
    missing = overlay.subtract([bounds(block)], direct)
    return {label: overlay.intersect(missing, mask) for label, mask in masks.items()}


def resolver_witness(path):
    rows = []
    for row in tsv(path):
        if row["source_id"] != "v41-resolver-only-candidates" or row["family"] != "IPv4":
            continue
        # A count below the row's full size cannot identify WHICH addresses had DIRECT.
        if int(row["overlap_preblock_direct"]) == int(row["addresses"]):
            rows.append(ipaddress.IPv4Network(row["prefix"]))
    return overlay.intervals(rows, 4)


def as_text(ranges):
    return origins.as_cidrs(ranges, 4)


def stats(before, gain, categories):
    after = overlay.normalize_interval_union(before, gain)
    ru = overlay.networks_from_intervals(after, 4) | {n for n in categories["RU"] if n.version == 6}
    payload = overlay.encode_geoip({"RU": ru, "PRIVATE": categories["PRIVATE"]})
    return {"added_ipv4": overlay.interval_size(overlay.subtract(after, before)),
            "ipv4_cidrs": sum(n.version == 4 for n in ru), "dat_bytes": len(payload),
            "dat_sha256": sha256(payload).hexdigest()}


def partner_overlaps(ranges, providers):
    hits = ((label, overlay.intersect(ranges, mask)) for label, mask in providers.items())
    return {label: overlay.interval_size(parts) for label, parts in hits if parts}


def touching_cidrs(observed, final_ranges):
    touched = set()
    for lo, hi in observed:
        i = max(0, bisect_left(final_ranges, (lo, -1)) - 1)
        while i < len(final_ranges) and final_ranges[i][0] <= hi:
            if final_ranges[i][1] >= lo:
                touched.add(i)
            i += 1
    return len(touched)


def audit(snapshot, restored, providers_path=None, data=DATA, limit=15):
    policy_path = snapshot / origins.POLICY
    manifest = json.loads(policy_path.read_bytes())
    pins = {origins.DAT: manifest["output_sha256"],
            REGIONAL: manifest["input_sha256"]["regional_origin_prefixes"],
            HARD: manifest["input_sha256"]["blocked_exact_and_legacy"]}
    for name, digest in pins.items():
        if origins.describe(snapshot / name)["sha256"] != digest:
            raise ValueError(f"snapshot digest mismatch: {name}")
    provenance = restored / origins.PROVENANCE
    if origins.describe(provenance)["sha256"] != manifest["input_provenance_sha256"]:
        raise ValueError("provenance does not match policy manifest")
    archive = restored / origins.ARCHIVE
    with redirect_stdout(sys.stderr):
        origins.verify_archive(provenance, archive)
    categories = overlay.parse_geoip_dat(snapshot / origins.DAT)
    before = overlay.intervals(categories["RU"], 4)
    private = overlay.intervals(categories["PRIVATE"], 4)
    regional = delegated_asns(restored)
    company = read_company_registry(data / "geoip_RU_company_asns.tsv")
    policy = read_policy(data / "geoip_RU_company_asn_policy.tsv", company)
    blocks = fragment_blocks(categories["RU"])
    by_origin, by_block, info = observations(archive, regional, company, blocks)

    telegram = overlay.intervals(read_telegram_feed(restored / "telegram-official-cidrs.txt"), 4)
    hard = overlay.intervals(v4_networks(snapshot / HARD), 4)
    unconditional = overlay.normalize_interval_union(hard, telegram)
    effective = overlay.intervals(v4_networks(snapshot / EFFECTIVE), 4)
    if overlay.subtract(unconditional, effective) or overlay.intersect(before, effective):
        raise ValueError("snapshot effective masks are inconsistent with hard masks or final RU")
    soft = overlay.subtract(effective, unconditional)
    subnet = overlay.intersect(hard, overlay.intervals(v4_networks(restored / "antifilter-subnet.lst"), 4))
    rkn = overlay.intersect(hard, overlay.intervals(
        (ipaddress.IPv4Network(row["CIDR"], strict=False) for row in tsv(data / "v41-reviewed-rkn-ip-records.tsv")
         if row.get("CIDR") and ":" not in row["CIDR"]), 4))
    named_hard = overlay.normalize_interval_union(subnet, rkn)
    admission = overlay.intervals(
        (ipaddress.ip_network(r["prefix"]) for r in tsv(data / "v41-regional-admission-exclusions.tsv")), 4)
    reviewed = overlay.intervals(
        (ipaddress.ip_network(r["cidr"]) for r in tsv(data / "v41-reviewed-unreachable.tsv")), 4)
    protected = overlay.normalize_interval_union(private, unconditional, admission, reviewed)
    resolver_provenance = snapshot / "geoip_RU_v41_blocked_provenance.tsv"
    witnessed = overlay.intersect(overlay.subtract(soft, protected), resolver_witness(resolver_provenance))
    selected = overlay.intervals(v4_networks(snapshot / REGIONAL), 4)
    if overlay.intersect(selected, soft):
        raise ValueError("resolver-only effective mask unexpectedly cuts selected regional/company origins")
    masks = {"private": private, "telegram": telegram, "subnet": subnet, "reviewed_rkn": rkn,
             "other_hard": overlay.subtract(hard, named_hard), "regional_admission": admission,
             "reviewed_unreachable": reviewed, "resolver_only": soft, "resolver_preblock_witness": witnessed}
    provider_meta, provider_ranges = {}, {}
    if providers_path:
        meta, providers = load_snapshot(providers_path)
        if meta["catalog_sha256"] != origins.describe(data / "v41-audit-global-networks.json")["sha256"]:
            raise ValueError("provider snapshot uses a different catalog")
        provider_meta = {"status": meta["status"], "fetched_at": meta["fetched_at"],
                         "payload_sha256": {u: f["sha256"] for u, f in meta["files"].items()}}
        provider_ranges = {label: overlay.intervals(nets, 4) for label, (_, nets) in providers.items() if nets is not None}

    rows = []
    for block, parts in blocks.items():
        direct = overlay.intervals(parts, 4)
        asn, unobserved = single_origin(block, direct, by_block[block])
        if asn not in info:
            continue
        gaps = classify_gaps(block, direct, masks)
        unexplained = overlay.subtract(overlay.subtract([bounds(block)], direct),
                                       overlay.normalize_interval_union(protected, soft))
        rows.append({"block": str(block), "asn": asn, **info[asn], "cidrs": len(parts),
                     "covered_ipv4": overlay.interval_size(direct), "block_ipv4": block.num_addresses,
                     "gaps": {k: as_text(v) for k, v in gaps.items() if v},
                     "unexplained": as_text(unexplained),
                     "no_ipverse_origin": as_text(unobserved),
                     "exact_parent_origin": any(n == block and a == asn for a, n in by_block[block]),
                     "any_covering_origin": any(block.subnet_of(n) and a == asn for a, n in by_block[block]),
                     "global_provider_overlap": partner_overlaps([bounds(block)], provider_ranges)})
    rows.sort(key=lambda r: (-r["cidrs"], ipaddress.IPv4Network(r["block"])))

    baseline = stats(before, [], categories)
    if baseline["dat_sha256"] != manifest["output_sha256"]:
        raise ValueError("canonical baseline DAT cannot be reproduced")
    findings, country_only, protected_examples = [], [], []
    checked = Counter()
    final_ranges = sorted(bounds(n) for n in categories["RU"] if n.version == 4)
    example_asns = {r["asn"] for r in rows[:limit]} - policy.keys()
    for asn, prefixes in sorted(by_origin.items()):
        if asn in policy:
            continue
        observed = overlay.intervals(prefixes, 4)
        is_regional = asn in regional
        checked["RIR regional" if is_regional else "ipverse country only"] += 1
        dns = overlay.intersect(observed, witnessed)
        if is_regional:
            if overlay.subtract_ranges(observed, selected) or dns:
                raise ValueError(f"regional origin AS{asn} is not covered by the current resolver protection")
            if asn in example_asns:
                protected_examples.append({"asn": asn, **info[asn],
                    "current_ipv4_cidrs_intersected": touching_cidrs(observed, final_ranges),
                    "hard_ipv4": overlay.interval_size(overlay.intersect(observed, unconditional))})
            continue
        observation = {"asn": asn, **info[asn], "raw_ipv4_routes": len(prefixes),
                       "current_ipv4_cidrs_intersected": touching_cidrs(observed, final_ranges),
                       "observed_ipv4": overlay.interval_size(observed),
                       "effective_resolver_ipv4": overlay.interval_size(overlay.intersect(observed, soft)),
                       "resolver_preblock_witness_ipv4": overlay.interval_size(dns)}
        country_only.append(observation)
        if not dns:
            continue
        add = overlay.subtract(overlay.subtract(observed, protected), before)
        if overlay.subtract(dns, add):
            raise ValueError("DNS witness is not a subset of the simulated addition")
        full_stats, dns_stats = (stats(before, delta, categories) for delta in (add, dns))
        findings.append({**observation, "dns_only": dns_stats, "full_ipv4_model": full_stats,
                         "dns_cidrs": as_text(dns), "other_added_addresses": overlay.interval_size(overlay.subtract(add, dns)),
                         "full_addition_global_provider_overlap": partner_overlaps(add, provider_ranges)})
    findings.sort(key=lambda r: (r["dns_only"]["ipv4_cidrs"], -r["dns_only"]["added_ipv4"], r["asn"]))
    return {"baseline": baseline, "candidates": findings, "examined_nonpolicy": dict(checked),
            "protected_examples": protected_examples, "ipverse_country_only": country_only,
            "company_policy_asns": len(policy), "raw_fragment_blocks": len(blocks),
            "single_origin_blocks": len(rows),
            "fragment_cause_sets": dict(Counter(",".join(sorted(r["gaps"])) or "no_mask" for r in rows)),
            "fragments": rows[:limit], "providers": provider_meta,
            "digests": {name: origins.describe(snapshot / name)["sha256"]
                        for name in (origins.DAT, origins.POLICY, REGIONAL, HARD, EFFECTIVE, resolver_provenance.name)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True, help="Files from the pinned Git release commit")
    parser.add_argument("--restored", type=Path, required=True, help="Inputs verified by verify_v41_snapshot_replay.py")
    parser.add_argument("--providers", type=Path, help="Optional global provider snapshot for negative screening")
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    print(json.dumps(audit(args.snapshot, args.restored, args.providers, limit=args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
