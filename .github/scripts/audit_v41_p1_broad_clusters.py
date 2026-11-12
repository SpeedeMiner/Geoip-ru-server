#!/usr/bin/env python3
"""Cluster P1 broad-only DIRECT hard conflicts by exact observed host prefixes.

A /16 grouping is an audit workload index, NOT a claim that the full /16 is
blocked, belongs to a service, or should be redirected.
"""
from __future__ import annotations

import argparse
import csv
import ipaddress
import json
from collections import Counter, defaultdict
from pathlib import Path


def cluster(rows):
    broad = []
    seen = set()
    for row in rows:
        host = ipaddress.ip_network(row["host"], strict=True)
        if host.version != 4 or host.prefixlen != 32 or str(host) in seen:
            raise ValueError(f"Invalid / duplicate IPv4 host: {host}")
        seen.add(str(host))
        if row["service_specificity_tier"] == "P1_BROAD_ONLY":
            if row["current_ip_lst"] != "YES" or row["origin_class"] not in ("SHARED_INFRA", "OTHER"):
                raise ValueError(f"Inconsistent broad-only P1: {host}")
            if not row["broad_24_or_wider_service_sources"] or row["exact_32_service_sources"]:
                raise ValueError(f"Broad-only P1 has inconsistent service evidence: {host}")
            broad.append(row)
    reports = []
    for length in (16, 20, 24):
        buckets = defaultdict(list)
        for row in broad:
            cidr = str(ipaddress.ip_network(f"{row['host'].split('/')[0]}/{length}", strict=False))
            buckets[cidr].append(row)
        for prefix, items in buckets.items():
            sources = Counter(s.strip() for row in items
                for s in row["broad_24_or_wider_service_sources"].split(",") if s.strip())
            classes = Counter(row["origin_class"] for row in items)
            reports.append({
                "group_prefix": prefix,
                "group_prefix_length": length,
                "exact_conflict_hosts": len(items),
                "shared_hosts": classes["SHARED_INFRA"],
                "other_hosts": classes["OTHER"],
                "source_membership_counts_nonexclusive": ";".join(
                    f"{name}:{count}" for name, count in sorted(sources.items())),
                "hosts": ",".join(sorted((r["host"] for r in items),
                                  key=lambda h: int(ipaddress.ip_network(h).network_address))),
                "scope": "REVIEW_ONLY_NOT_A_BLOCKED_SUBNET",
            })
    reports.sort(key=lambda r: (r["group_prefix_length"],
              -r["exact_conflict_hosts"], int(ipaddress.ip_network(r["group_prefix"]).network_address)))
    top = [row for row in reports if row["group_prefix_length"] == 16][:10]
    return reports, {
        "broad_only_current_hard_hosts": len(broad),
        "unique_ipv4_16_groups": sum(r["group_prefix_length"] == 16 for r in reports),
        "unique_ipv4_20_groups": sum(r["group_prefix_length"] == 20 for r in reports),
        "unique_ipv4_24_groups": sum(r["group_prefix_length"] == 24 for r in reports),
        "top_ipv4_16_groups": [{"prefix": r["group_prefix"], "hosts": r["exact_conflict_hosts"]}
                               for r in top],
        "automatic_subnet_carving": False,
        "grouping_proves_all_hosts_blocked": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p1", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    with args.p1.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file, delimiter="\t"))
    if not rows:
        raise ValueError("Empty P1 audit queue")
    report, stats = cluster(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "p1_broad_only_host_clusters.tsv").open(
            "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(report[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(report)
    (args.output_dir / "p1_broad_only_cluster_summary.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
