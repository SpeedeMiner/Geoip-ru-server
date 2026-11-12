#!/usr/bin/env python3
"""Read-only v41 audit: exact service/ASN evidence for legacy hard overrides."""
from __future__ import annotations

import argparse
import csv
import ipaddress
import json
from pathlib import Path

from build_v41_overlay import load_service_inputs, parse_cidr_file


def most_specific_containing(ip, prefixes):
    matches = (net for net in prefixes if net.version == ip.version and ip in net)
    return sorted(matches, key=lambda net: (-net.prefixlen, int(net.network_address)))


def classify_override(ip, sources, core, shared):
    result = {
        "core_prefix": str(most_specific_containing(ip, core)[0]) if most_specific_containing(ip, core) else "",
        "shared_prefix": str(most_specific_containing(ip, shared)[0]) if most_specific_containing(ip, shared) else "",
    }
    for name in sorted(sources):
        matches = most_specific_containing(ip, sources[name])
        result[name] = str(matches[0]) if matches else ""
        result[name + "_broadest"] = str(matches[-1]) if matches else ""
    service_hits = [name for name in sorted(sources) if result[name]]
    result["service_inputs"] = ",".join(service_hits)
    result["service_match_count"] = len(service_hits)
    result["shared_with_service_overlap"] = bool(result["shared_prefix"] and service_hits)
    # A host-/32 match is materially narrower than an entire /16--/24 cloud prefix.
    result["broad_service_match"] = any(
        any(net.prefixlen <= 24 for net in most_specific_containing(ip, sources[name]))
        for name in service_hits
    )
    result["decision"] = "REVIEW_ONLY"
    return result


def load_pinned_sources(args):
    class Inputs:
        pass
    feed = Inputs()
    feed.kyoresuas_v4 = args.kyoresuas_v4
    feed.kyoresuas_v6 = args.kyoresuas_v6
    feed.kyoresuas_services = args.kyoresuas_services
    feed.w1zardz = args.w1zardz
    feed.hxehex_ip = args.hxehex_ip
    feed.escapingworm = args.escapingworm
    sources, _, _ = load_service_inputs(feed)
    core, _ = parse_cidr_file(args.core_prefixes, allow_hosts=False)
    shared, _ = parse_cidr_file(args.shared_prefixes, allow_hosts=False)
    return sources, core, shared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in (
        "overrides", "core_prefixes", "shared_prefixes", "kyoresuas_v4",
        "kyoresuas_v6", "kyoresuas_services", "w1zardz", "hxehex_ip",
        "escapingworm", "output_dir",
    ):
        parser.add_argument("--" + field.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    sources, core, shared = load_pinned_sources(args)
    with args.overrides.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    if len(rows) != 9:
        raise ValueError(f"Expected nine historical hard exceptions, found {len(rows)}")
    report = []
    for row in rows:
        if row["still_effective_block"] != "NO" or row["in_v41_direct"] != "YES":
            raise ValueError(f"Expected genuine unblocked DIRECT exception: {row['prefix']}")
        host = ipaddress.ip_network(row["prefix"], strict=True)
        if host.version != 4 or host.prefixlen != 32:
            raise ValueError(f"Expected exact IPv4 host: {host}")
        reason = classify_override(host.network_address, sources, core, shared)
        if not reason["service_inputs"] and not reason["core_prefix"]:
            raise ValueError(f"Override lacks any pinned source evidence: {host}")
        report.append({"prefix": str(host), **reason})
    if len([row for row in report if row["shared_with_service_overlap"]]) != 6:
        raise ValueError("Known six shared-service hard overrides changed; review upstream evidence")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    names = list(report[0])
    with (args.output_dir / "nine_legacy_hard_service_overrides.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=names)
        writer.writeheader()
        writer.writerows(report)
    summary = {
        "total_hard_overrides": len(report),
        "shared_infrastructure_with_service_exception": sum(row["shared_with_service_overlap"] for row in report),
        "broad_service_match": sum(row["broad_service_match"] for row in report),
        "core_corporate": sum(bool(row["core_prefix"]) for row in report),
        "service_source_coverage": {name: sum(bool(row[name]) for row in report) for name in sorted(sources)},
        "status": "REVIEW_ONLY",
    }
    (args.output_dir / "nine_override_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
