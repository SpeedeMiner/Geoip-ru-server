#!/usr/bin/env python3
"""Independent v41 class-aware protobuf and block-precedence validator."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import ipaddress
from pathlib import Path

import build_v41_overlay as builder


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(args: argparse.Namespace) -> dict:
    decoded = builder.parse_geoip_dat(args.geoip)
    if set(decoded) != {"RU", "PRIVATE"}:
        raise ValueError(f"GeoIP must contain exactly RU and PRIVATE, got {sorted(decoded)}")

    blocked_union = builder.parse_cidr_file(args.blocked_union)[0]
    blocked_exact = builder.parse_cidr_file(args.blocked_exact)[0]
    blocked_resolved = builder.parse_cidr_file(args.blocked_resolved)[0]
    company_all = builder.parse_cidr_file(args.company_all, allow_hosts=False)[0]
    company_core = builder.parse_cidr_file(args.company_core, allow_hosts=False)[0]
    shared = builder.parse_cidr_file(args.company_shared, allow_hosts=False)[0]
    regional_all = builder.parse_cidr_file(args.regional_origin_prefixes, allow_hosts=False)[0]
    regional_only = builder.subtract_networks(regional_all, company_all)
    # Use the exact same v39 service-source classification, reconstructed from the
    # pinned service feeds for independent validation.
    class Inputs: pass
    feeds = Inputs()
    feeds.kyoresuas_v4 = args.kyoresuas_v4
    feeds.kyoresuas_v6 = args.kyoresuas_v6
    feeds.kyoresuas_services = args.kyoresuas_services
    feeds.w1zardz = args.w1zardz
    feeds.hxehex_ip = args.hxehex_ip
    feeds.escapingworm = args.escapingworm
    service_sources, _, _ = builder.load_service_inputs(feeds)
    rir_resources, _ = builder.parse_rir_tsv(args.rir)
    _, service_protected = builder.build_ru_service_protection_mask(
        set(), rir_ru=rir_resources["RU"], service_sources=service_sources
    )
    if company_core & shared or company_core | shared != company_all:
        raise ValueError("Company core/shared masks are not a disjoint exact partition")
    if any(builder.intervals(blocked_union, version) != builder.intervals(blocked_exact | blocked_resolved, version) for version in (4, 6)):
        raise ValueError("Approved blocked address-space union differs from exact + resolver sidecars")

    effective, resolved_only = builder.class_aware_effective_block_set(
        blocked_exact, blocked_resolved, company_core, shared, regional_only, service_protected
    )
    output_blocked = builder.parse_cidr_file(args.effective_blocked)[0]
    if output_blocked != effective:
        raise ValueError("Published v41 effective block output differs from the class-aware policy calculation")

    for version in (4, 6):
        ru_iv = builder.intervals(decoded["RU"], version)
        private_iv = builder.intervals(decoded["PRIVATE"], version)
        blocked_iv = builder.intervals(output_blocked, version)
        exact_iv = builder.intervals(blocked_exact, version)
        core_iv = builder.intervals(company_core, version)
        shared_iv = builder.intervals(shared, version)
        regional_iv = builder.intervals(regional_only, version)
        service_iv = builder.intervals(service_protected, version)
        if builder.intersect(ru_iv, private_iv):
            raise ValueError(f"RU intersects PRIVATE in IPv{version}")
        if builder.intersect(ru_iv, blocked_iv):
            raise ValueError(f"RU intersects effective blocked set in IPv{version}")

        core_expected = builder.subtract(core_iv, private_iv)
        core_missing = builder.subtract(core_expected, ru_iv)
        if core_missing:
            raise ValueError(f"CORE_CORPORATE prefix coverage lost in IPv{version}")

        shared_expected = builder.subtract(shared_iv, private_iv)
        shared_expected = builder.subtract(shared_expected, exact_iv)
        shared_missing = builder.subtract(shared_expected, ru_iv)
        if shared_missing:
            raise ValueError(f"SHARED_INFRA resolver-only protection coverage lost in IPv{version}")
        regional_expected = builder.subtract(regional_iv, private_iv)
        regional_expected = builder.subtract(regional_expected, exact_iv)
        if builder.subtract(regional_expected, ru_iv):
            raise ValueError(f"RIR-RU selected origin resolver-only protection lost in IPv{version}")
        service_expected = builder.subtract(service_iv, private_iv)
        if builder.subtract(service_expected, ru_iv):
            raise ValueError(f"Verified RU service protection lost in IPv{version}")

        # A shared provider may overlap an exact/legacy hard block, but no
        # resolver-only candidate may remain blocked inside a shared prefix.
        blocked_shared = builder.intersect(blocked_iv, shared_iv)
        allowed_shared_hard = builder.intersect(blocked_shared, exact_iv)
        if builder.subtract(blocked_shared, allowed_shared_hard):
            raise ValueError(f"Effective block intersects SHARED_INFRA outside exact/legacy hard blocks in IPv{version}")

    # Independent full set inclusion check: all Hydra DIRECT/WHITELIST entries
    # must survive except PRIVATE and the effective v41 blocked set.
    hydra_sources = builder.parse_hydra_direct_whitelist(args.hydra)
    expected_hydra = builder.hydra_expected_after_policy(hydra_sources, decoded["PRIVATE"], output_blocked)
    for version in (4, 6):
        if builder.subtract(builder.intervals(expected_hydra, version), builder.intervals(decoded["RU"], version)):
            raise ValueError(f"Hydra DIRECT/WHITELIST IPv{version} eligible coverage missing")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("input_sha256", {}).get("hydra_geoip") != sha256(args.hydra):
        raise ValueError("Hydra input SHA-256 mismatch")
    if manifest.get("hydra_routing_intent", {}).get("input_sha256") != sha256(args.hydra):
        raise ValueError("Hydra provenance SHA-256 mismatch")
    if manifest.get("safety", {}).get("hydra_direct_whitelist_added_without_block_exemption") is not True:
        raise ValueError("Hydra precedence safety flag missing")
    if manifest.get("output_sha256") != sha256(args.geoip):
        raise ValueError("Manifest output SHA-256 does not match GeoIP protobuf")
    if manifest.get("input_sha256", {}).get("corporate_company_asn_origin_prefixes") != sha256(args.company_all):
        raise ValueError("Manifest all-company prefix SHA-256 mismatch")
    if manifest.get("input_sha256", {}).get("corporate_core_prefixes") != sha256(args.company_core):
        raise ValueError("Manifest CORE_CORPORATE prefix SHA-256 mismatch")
    if manifest.get("input_sha256", {}).get("shared_infrastructure_prefixes") != sha256(args.company_shared):
        raise ValueError("Manifest SHARED_INFRA prefix SHA-256 mismatch")
    if manifest.get("input_sha256", {}).get("blocked_exact_and_legacy") != sha256(args.blocked_exact):
        raise ValueError("Manifest exact/legacy block SHA-256 mismatch")
    if manifest.get("input_sha256", {}).get("blocked_resolver_only") != sha256(args.blocked_resolved):
        raise ValueError("Manifest resolver-only block SHA-256 mismatch")
    if manifest.get("input_sha256", {}).get("regional_origin_prefixes") != sha256(args.regional_origin_prefixes):
        raise ValueError("Manifest selected RIR-RU origin SHA-256 mismatch")

    safety = manifest.get("safety", {})
    required_flags = {
        "private_precedence_applied": True,
        "core_corporate_prefixes_remain_direct_except_private": True,
        "shared_infrastructure_prefixes_exempt_from_current_ipresolve_only": True,
        "rkn_exact_ip_and_subnet_blocks_apply_to_shared_infrastructure": True,
        "legacy_v38_unclassified_baseline_remains_hard_blocked": True,
        "rir_ru_selected_origin_resolver_protected": True,
        "ru_verified_service_exact_and_resolver_protected": True,
        "private_precedence_over_all_exceptions": True,
        "ipsum_24_auto_carved": False,
    }
    for key, expected in required_flags.items():
        if safety.get(key) is not expected:
            raise ValueError(f"Missing or incorrect v41 policy safety flag: {key}={safety.get(key)!r}")

    ipsum_carved = manifest.get("blocked", {}).get("ipsum_auto_carved")
    if ipsum_carved is not False:
        raise ValueError("v41 must keep ipsum /24 summaries review-only")

    countries = set()
    with args.rir.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            countries.add(row["country"])
    if countries != {"RU", "BY", "KZ"}:
        raise ValueError(f"RIR resource inventory country set mismatch: {countries}")

    quality = args.quality.read_text(encoding="utf-8")
    for marker in (
        "CORE_CORPORATE",
        "SHARED_INFRA",
        "Antifilter ipsum REVIEW-ONLY IPv4 /24 prefixes",
        "RIR-RU registration alone does not imply corporate ownership",
    ):
        if marker not in quality:
            raise ValueError(f"v41 quality report missing policy marker: {marker}")

    report = {
        "geoip_bytes": args.geoip.stat().st_size,
        "geoip_sha256": sha256(args.geoip),
        "ru_cidrs": len(decoded["RU"]),
        "private_cidrs": len(decoded["PRIVATE"]),
        "approved_blocked_prefixes": len(blocked_union),
        "effective_blocked_prefixes": len(output_blocked),
        "exact_hard_prefixes": len(blocked_exact),
        "current_resolver_only_prefixes": len(resolved_only),
        "company_prefixes": len(company_all),
        "core_company_prefixes": len(company_core),
        "shared_infrastructure_prefixes": len(shared),
        "rir_ru_additional_origin_prefixes": len(regional_only),
        "verified_ru_service_prefixes": len(service_protected),
        "hydra_direct_prefixes": len(hydra_sources["hydra-direct"]),
        "hydra_whitelist_prefixes": len(hydra_sources["hydra-whitelist"]),
        "status": "VALID",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "geoip", "hydra", "blocked_union", "blocked_exact", "blocked_resolved",
        "company_all", "company_core", "company_shared", "regional_origin_prefixes",
        "kyoresuas_v4", "kyoresuas_v6", "kyoresuas_services", "w1zardz",
        "hxehex_ip", "escapingworm", "effective_blocked",
        "manifest", "quality", "rir",
    ):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
