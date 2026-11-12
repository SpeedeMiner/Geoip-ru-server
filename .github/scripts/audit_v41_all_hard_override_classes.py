#!/usr/bin/env python3
"""Read-only classification of every hard IP exclusion still present in GeoIP v41 RU.

Classify by CORE, SHARED, or other infrastructure and by presence of verified
service protection. Use exact interval algebra including IPv6; never infer
that raw hard-source rows prove active regulatory blocks.
"""
from __future__ import annotations

import argparse
import csv
import ipaddress
import json
from pathlib import Path

from build_v41_overlay import (
    intersect, interval_size, intervals, networks_from_intervals, parse_cidr_file,
    parse_geoip_dat, load_service_inputs,
)
from audit_v41_legacy_hard_evidence import tagged_networks, effective_networks
from audit_v41_service_hard_overrides import load_pinned_sources


def partition_overrides(ru, hard_rows, effective, core, shared, service_sources):
    hard = {net for net, _ in hard_rows}
    service = set().union(*service_sources.values())
    groups = {}
    masks = {"CORE_CORPORATE": core, "SHARED_INFRA": shared}
    for version in (4, 6):
        ru_iv = intervals(ru, version)
        hard_iv = intervals(hard, version)
        effective_iv = intervals(effective, version)
        core_iv = intervals(core, version)
        shared_iv = intervals(shared, version)
        service_iv = intervals(service, version)
        all_overrides = intersect(ru_iv, hard_iv)
        if intersect(all_overrides, effective_iv):
            raise ValueError("DIRECT and effective hard blocks overlap")
        # Partition with precedence: CORE first, SHARED second, then other.
        from build_v41_overlay import subtract
        core_overrides = intersect(all_overrides, core_iv)
        shared_overrides = subtract(intersect(all_overrides, shared_iv), core_overrides)
        other_overrides = subtract(subtract(all_overrides, core_overrides), shared_overrides)
        split = {
            "CORE_CORPORATE": core_overrides,
            "SHARED_INFRA": shared_overrides,
            "OTHER": other_overrides,
        }
        if sum(interval_size(x) for x in split.values()) != interval_size(all_overrides):
            raise ValueError("Partition lost or duplicated hard-override address space")
        results = {}
        for name, values in split.items():
            in_service = intersect(values, service_iv)
            results[name] = {
                "addresses": interval_size(values),
                "cidrs": len(networks_from_intervals(values, version)),
                "also_verified_service_addresses": interval_size(in_service),
                "without_verified_service_addresses": interval_size(values) - interval_size(in_service),
                "intervals": values,
            }
        groups[version] = {"total_addresses": interval_size(all_overrides),
                           "total_cidrs": len(networks_from_intervals(all_overrides, version)),
                           "by_origin_class": results}
    return groups


def write_results(output_dir, summary):
    output_dir.mkdir(parents=True, exist_ok=True)
    clean = {"policy": "READ_ONLY_HARD_OVERRIDES_ALL_ASN_CLASSES",
             "routing_modified": False, "by_family": {}}
    for version, stats in summary.items():
        data = {"total_addresses": stats["total_addresses"], "total_cidrs": stats["total_cidrs"],
                "by_origin_class": {}}
        for name, values in stats["by_origin_class"].items():
            data["by_origin_class"][name] = {
                key: val for key, val in values.items() if key != "intervals"
            }
            with (output_dir / f"ipv{version}_hard_overrides_{name.lower()}.txt").open("w", encoding="utf-8") as f:
                nets = networks_from_intervals(values["intervals"], version)
                for net in sorted(nets, key=lambda x: (int(x.network_address), x.prefixlen)):
                    f.write(str(net) + "\n")
        clean["by_family"][f"ipv{version}"] = data
    (output_dir / "all_hard_override_classes_summary.json").write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(clean, ensure_ascii=False, sort_keys=True))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("hard", "effective", "v41", "core_prefixes", "shared_prefixes",
                 "kyoresuas_v4", "kyoresuas_v6", "kyoresuas_services", "w1zardz",
                 "hxehex_ip", "escapingworm", "output_dir"):
        p.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = p.parse_args()
    decoded = parse_geoip_dat(args.v41)
    if set(decoded) != {"RU", "PRIVATE"}:
        p.error("Unexpected v41 categories")
    services, core, shared = load_pinned_sources(args)
    result = partition_overrides(decoded["RU"], tagged_networks(args.hard),
                                 effective_networks(args.effective), core, shared, services)
    write_results(args.output_dir, result)


if __name__ == "__main__":
    main()
