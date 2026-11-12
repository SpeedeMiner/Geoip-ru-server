#!/usr/bin/env python3
"""Warn on new shared-infra IPv4 hard-host overrides by broad service masks.

This is a READ-ONLY diagnostic, not a mechanism for approving, restoring or
subtracting any routing entries. An established observation is NOT an approval.
"""
from __future__ import annotations

import argparse
import csv
import ipaddress
import json
from bisect import bisect_right
from pathlib import Path

from audit_v41_legacy_hard_evidence import effective_networks, tagged_networks
from audit_v41_service_hard_overrides import classify_override, load_pinned_sources
from build_v41_overlay import intervals, parse_geoip_dat


def contains(ip, ranges, starts):
    idx = bisect_right(starts, int(ip)) - 1
    return idx >= 0 and int(ip) <= ranges[idx][1]


def lookup(networks):
    spans = intervals(networks, 4)
    return spans, [x[0] for x in spans]


def load_observed_baseline(path):
    with path.open(encoding="utf-8", newline="") as fh:
        lines = list(csv.DictReader(fh, delimiter="\t"))
    if not lines or set(lines[0]) != {"prefix", "basis"}:
        raise ValueError("Expected nonempty baseline with prefix and basis")
    observed = {}
    for row in lines:
        net = ipaddress.ip_network(row["prefix"], strict=True)
        if net.version != 4 or net.prefixlen != 32 or not row["basis"].strip():
            raise ValueError("Baseline must document exact IPv4 host evidence")
        if str(net) in observed:
            raise ValueError("Duplicate baseline IP")
        observed[str(net)] = row["basis"]
    return observed


def scan(hard, effective, direct, sources, core, shared, baseline):
    direct_range, direct_starts = lookup(direct)
    blocked_range, blocked_starts = lookup(effective)
    shared_range, shared_starts = lookup(shared)
    broad_by_source = {
        name: {net for net in values if net.version == 4 and net.prefixlen <= 24}
        for name, values in sources.items()
    }
    broad_range, broad_starts = lookup(
        set().union(*broad_by_source.values())
    )
    hard_by_ip = {}
    for net, tags in hard:
        if net.version != 4 or net.prefixlen != 32:
            continue
        hard_by_ip.setdefault(str(net), set()).update(tags)
    flagged = []
    for prefix, tags in hard_by_ip.items():
        ip = ipaddress.ip_network(prefix).network_address
        if not contains(ip, shared_range, shared_starts):
            continue
        if not contains(ip, broad_range, broad_starts):
            continue
        if contains(ip, blocked_range, blocked_starts):
            continue
        if not contains(ip, direct_range, direct_starts):
            continue
        evidence = classify_override(ip, sources, core, shared)
        if not evidence["shared_with_service_overlap"] or not evidence["broad_service_match"]:
            raise ValueError(f"Unexpected evidence inconsistency: {prefix}")
        flagged.append({
            "prefix": prefix,
            "evidence_sources": ",".join(sorted(tags)),
            "shared_prefix": evidence["shared_prefix"],
            "broad_service_sources": ",".join(
                name for name, prefixes in sorted(broad_by_source.items())
                if any(ip in p for p in prefixes)
            ),
            "service_matches": evidence["service_inputs"],
            "known_observation": "YES" if prefix in baseline else "NO",
            "observed_baseline_note": baseline.get(prefix, ""),
        })
    flagged.sort(key=lambda row: int(ipaddress.ip_network(row["prefix"]).network_address))
    found = {row["prefix"] for row in flagged}
    new = sorted(found - baseline.keys(), key=lambda x: int(ipaddress.ip_network(x).network_address))
    disappeared = sorted(baseline.keys() - found)
    result = {
        "all_hard_ipv4_32_unique": len(hard_by_ip),
        "shared_broad_service_hard_overrides": len(flagged),
        "new_unreviewed_hard_overrides": len(new),
        "new_unreviewed_prefixes": new,
        "previously_observed_not_current": disappeared,
        "baseline_observed_not_approved": True,
        "scope": "audit_only_no_production_change",
    }
    return flagged, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("hard", "effective", "v41", "baseline", "core_prefixes",
                 "shared_prefixes", "kyoresuas_v4", "kyoresuas_v6",
                 "kyoresuas_services", "w1zardz", "hxehex_ip",
                 "escapingworm", "output_dir"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    sources, core, shared = load_pinned_sources(args)
    decoded = parse_geoip_dat(args.v41)
    if set(decoded) != {"RU", "PRIVATE"}:
        raise ValueError("Expected released RU and PRIVATE categories")
    baseline = load_observed_baseline(args.baseline)
    rows, summary = scan(
        tagged_networks(args.hard), effective_networks(args.effective),
        decoded["RU"], sources, core, shared, baseline
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "all_shared_service_hard_overrides.tsv"
    fields = ("prefix", "evidence_sources", "shared_prefix", "broad_service_sources",
              "service_matches", "known_observation", "observed_baseline_note")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (args.output_dir / "shared_service_hard_guard_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    if summary["new_unreviewed_hard_overrides"]:
        print("::warning title=New SHARED broad-service hard exceptions::"
              + f"{summary['new_unreviewed_hard_overrides']} newly observed hard-host exceptions: "
              + ", ".join(summary["new_unreviewed_prefixes"][:15])
              + ". Review report; baseline entries are not approvals.")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
