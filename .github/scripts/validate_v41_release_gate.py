#!/usr/bin/env python3
"""Fail-closed v41 pre-publication hard/DIRECT policy gate.

Use only this *build's* inputs and manifest. The permitted exceptions are
CORE_CORPORATE and the precise service protection mask reconstructed from
current source data. Current Antifilter hard-source membership is provenance,
NOT independent proof of an active legal IP block. No remote API calls.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path

import build_v41_overlay as builder

REPORT_MARKER = "PRE_PUBLICATION_V41_HARD_POLICY_GATE"
SOURCE_KEYS = {
    "hard": "blocked_exact_and_legacy",
    "core": "corporate_core_prefixes",
    "shared": "shared_infrastructure_prefixes",
    "rir": "regional_rir_inventory",
    "kyoresuas_v4": "kyoresuas_standard_ipv4",
    "kyoresuas_v6": "kyoresuas_standard_ipv6",
    "kyoresuas_services": "kyoresuas_services_json",
    "w1zardz": "w1zardz_direct",
    "hxehex_ip": "hxehex_ipwhitelist",
    "escapingworm": "escapingworm_operator_whitelist",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_manifest(manifest: dict, args) -> None:
    if manifest.get("schema") != 2:
        raise ValueError("unexpected v41 manifest schema")
    if manifest.get("output_sha256") != digest(args.geoip):
        raise ValueError("GeoIP SHA-256 does not match current build manifest")
    recorded = manifest.get("input_sha256")
    if not isinstance(recorded, dict):
        raise ValueError("missing manifest input SHA-256 mapping")
    for field, key in SOURCE_KEYS.items():
        if recorded.get(key) != digest(getattr(args, field)):
            raise ValueError(f"build input SHA-256 mismatch: {key}")


def read_hard_sources(path: Path):
    rows = []
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        prefix, sep, provenance = line.partition("#")
        if not sep or not provenance.strip().startswith("sources="):
            raise ValueError(f"hard source row {number} is missing provenance")
        net = ipaddress.ip_network(prefix.strip(), strict=True)
        tags = frozenset(x.strip() for x in provenance.strip()[len("sources="):].split(","))
        if "" in tags or not tags:
            raise ValueError(f"hard source row {number} has empty labels")
        rows.append((net, tags))
    if not rows:
        raise ValueError("hard source has no CIDR records")
    return rows


def inspect_policy(ru, private, effective, hard_rows, core, shared, service):
    """Exact disjoint address sets, not CIDR row counts. Raises on unsafe output."""
    hard = {prefix for prefix, _ in hard_rows}
    current_ip = {prefix for prefix, labels in hard_rows if "antifilter-ip.lst" in labels}
    current_subnet = {prefix for prefix, labels in hard_rows if "antifilter-subnet.lst" in labels}
    allowed = core | service
    result = {"status": "PASS", "policy": "PRIVATE > effective blocked > DIRECT",
              "hard_exceptions_are_observations_not_approval": True, "families": {}}
    for version in (4, 6):
        ru_i = builder.intervals(ru, version)
        if not ru_i:
            raise ValueError(f"missing IPv{version} RU category address space")
        if builder.intersect(ru_i, builder.intervals(private, version)):
            raise ValueError(f"IPv{version} DIRECT intersects PRIVATE")
        if builder.intersect(ru_i, builder.intervals(effective, version)):
            raise ValueError(f"IPv{version} DIRECT intersects effective blocked set")
        hard_direct = builder.intersect(ru_i, builder.intervals(hard, version))
        # This is the actionable strict safety condition: hard exceptions must
        # be explainable by the current, actual CORE or service policy mask.
        unjustified = builder.subtract(hard_direct, builder.intervals(allowed, version))
        if unjustified:
            ip = ipaddress.IPv4Address if version == 4 else ipaddress.IPv6Address
            raise ValueError(f"IPv{version} unprotected hard-block leak in DIRECT, "
                             f"first address={ip(unjustified[0][0])}")
        core_part = builder.intersect(hard_direct, builder.intervals(core, version))
        shared_part = builder.subtract(
            builder.intersect(hard_direct, builder.intervals(shared, version)), core_part)
        other_part = builder.subtract(builder.subtract(hard_direct, core_part), shared_part)
        partition = {
            "CORE_CORPORATE": core_part,
            "SHARED_INFRA": shared_part,
            "OTHER": other_part,
        }
        if sum(builder.interval_size(p) for p in partition.values()) != builder.interval_size(hard_direct):
            raise ValueError(f"IPv{version} hard exception class partition mismatch")
        summary = {}
        for name, addresses in partition.items():
            summary[name] = {
                "addresses": builder.interval_size(addresses),
                "current_antifilter_ip": builder.interval_size(
                    builder.intersect(addresses, builder.intervals(current_ip, version))),
                "current_antifilter_subnet": builder.interval_size(
                    builder.intersect(addresses, builder.intervals(current_subnet, version))),
                "service_protected": builder.interval_size(
                    builder.intersect(addresses, builder.intervals(service, version))),
            }
        result["families"][f"ipv{version}"] = {
            "hard_direct_overridden_addresses": builder.interval_size(hard_direct),
            "unprotected_hard_direct_addresses": 0,
            "classes": summary,
        }
    return result


def format_quality_section(result: dict) -> str:
    lines = ["", REPORT_MARKER, "Status: PASS",
             "Inputs: this build's SHA256-verified manifest, GeoIP, and source sidecars",
             "Policy: PRIVATE and effective hard blocks excluded from DIRECT",
             "Allowed hard exceptions: CORE_CORPORATE or current verified service-protection mask",
             "No hard exception is accepted solely due to SHARED_INFRA or BGP/ASN origin",
             "Exception source membership does not prove a current regulator IP block"]
    for family, summary in result["families"].items():
        lines.append(f"{family}: hard_direct={summary['hard_direct_overridden_addresses']}"
                     ", unprotected=0")
        for name, fields in summary["classes"].items():
            lines.append(f"  {name}: addresses={fields['addresses']}, "
                         f"current_ip_lst={fields['current_antifilter_ip']}, "
                         f"current_subnet_lst={fields['current_antifilter_subnet']}, "
                         f"service_protected={fields['service_protected']}")
    lines.append("Unresolved source conflicts: audit-only; no automatic changes to DIRECT")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("geoip", "manifest", "quality", "hard", "effective", "core",
                  "shared", "rir", "kyoresuas_v4", "kyoresuas_v6",
                  "kyoresuas_services", "w1zardz", "hxehex_ip", "escapingworm"):
        p.add_argument("--" + field.replace("_", "-"), type=Path, required=True)
    a = p.parse_args()
    try:
        manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
        check_manifest(manifest, a)
        categories = builder.parse_geoip_dat(a.geoip)
        if set(categories) != {"RU", "PRIVATE"}:
            raise ValueError("Expected GeoIP categories RU and PRIVATE only")
        effective = builder.parse_cidr_file(a.effective)[0]
        core = builder.parse_cidr_file(a.core, allow_hosts=False)[0]
        shared = builder.parse_cidr_file(a.shared, allow_hosts=False)[0]
        regions, _ = builder.parse_rir_tsv(a.rir)

        class CurrentFeeds:
            pass
        feed = CurrentFeeds()
        for field in ("kyoresuas_v4", "kyoresuas_v6", "kyoresuas_services",
                      "w1zardz", "hxehex_ip", "escapingworm"):
            setattr(feed, field, getattr(a, field))
        sources, _, _ = builder.load_service_inputs(feed)
        _, service = builder.build_ru_service_protection_mask(
            set(), rir_ru=regions["RU"], service_sources=sources)
        result = inspect_policy(categories["RU"], categories["PRIVATE"], effective,
                                read_hard_sources(a.hard), core, shared, service)

        original = a.quality.read_text(encoding="utf-8")
        if REPORT_MARKER in original:
            raise ValueError("release gate report marker already exists in quality report")
        a.quality.write_text(original.rstrip("\n") + "\n"
                             + format_quality_section(result), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        print(f"Updated release quality report: {a.quality}")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        p.exit(1, f"ERROR: v41 pre-publication policy gate: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
