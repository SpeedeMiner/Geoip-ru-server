#!/usr/bin/env python3
"""Shadow-only exact address delta if SHARED hard blocks outrank service protection.

No changes to artifacts, production, releases or routing. Source masks are
SHA256-pinned by the calling workflow before this script runs.
"""
from __future__ import annotations
import argparse
import csv
import ipaddress
import json
from pathlib import Path
from build_v41_overlay import (intersect, interval_size, intervals,
                              networks_from_intervals, parse_geoip_dat, parse_cidr_file)
from audit_v41_legacy_hard_evidence import tagged_networks, effective_networks


def calculate(ru, hard_rows, shared, effective):
    hard = {net for net, _ in hard_rows}
    current = {net for net, labels in hard_rows if "antifilter-ip.lst" in labels}
    legacy = {net for net, labels in hard_rows if "v38-baseline-hard-or-unclassified" in labels}
    results = {}
    overlaps = {}
    for version in (4, 6):
        ru_iv = intervals(ru, version)
        hard_iv = intervals(hard, version)
        shared_iv = intervals(shared, version)
        effective_iv = intervals(effective, version)
        shadow = intersect(intersect(ru_iv, shared_iv), hard_iv)
        if intersect(shadow, effective_iv):
            raise ValueError("Shadow override unexpectedly intersects effective block set")
        result = {
            "eligible_v41_direct_hard_shared_addresses": interval_size(shadow),
            "eligible_v41_direct_hard_shared_cidrs": len(networks_from_intervals(shadow, version)),
            "of_which_current_ip_lst_addresses": interval_size(intersect(shadow, intervals(current, version))),
            "of_which_legacy_v38_addresses": interval_size(intersect(shadow, intervals(legacy, version))),
        }
        results[f"ipv{version}"] = result
        overlaps[version] = shadow
    return results, overlaps


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("v41", "hard", "shared", "effective", "output_dir"):
        p.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    args = p.parse_args()
    decoded = parse_geoip_dat(args.v41)
    if set(decoded) != {"RU", "PRIVATE"}:
        p.error("Expected exactly RU and PRIVATE")
    shared = parse_cidr_file(args.shared, allow_hosts=False)[0]
    result, overlap = calculate(decoded["RU"], tagged_networks(args.hard), shared,
                                effective_networks(args.effective))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for version in (4, 6):
        with (args.output_dir / f"shadow_shared_hard_ipv{version}.txt").open("w", encoding="utf-8") as fh:
            for net in sorted(networks_from_intervals(overlap[version], version),
                              key=lambda n: (int(n.network_address), n.prefixlen)):
                fh.write(str(net) + "\n")
    report = {
        "policy": "SHADOW_ONLY_HARD_WINS_WITHIN_SHARED",
        "not_an_approved_routing_change": True,
        "contains_both_exact_hosts_and_broad_hard_prefixes": True,
        "addresses_by_family": result,
    }
    (args.output_dir / "shadow_shared_hard_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
