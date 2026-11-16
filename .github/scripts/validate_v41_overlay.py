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
from validate_v41_telegram import PINNED_FEED, read_telegram_feed
from v41_reviewed_ipv6_admission import verify_reviewed_ipv6_admission_manifest
from v41_reviewed_unreachable import DEFAULT_PATH as UNREACHABLE_PATH, read_reviewed
from v41_direct_admission import ROLE, cdn_networks, verify_cdn_manifest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_hxehex_diagnostic_only(ru, independently_admitted, hxehex):
    """No address from the diagnostic feed may enter RU without another input."""
    for version in (4, 6):
        candidates = builder.intersect(builder.intervals(ru, version),
                                       builder.intervals(hxehex, version))
        if builder.subtract(candidates, builder.intervals(independently_admitted, version)):
            raise ValueError(f"HXEHEX-only admission in IPv{version} DIRECT")


def verify_unreachable_manifest(manifest, regional, origins, companies, reviewed):
    records = read_reviewed()
    if (manifest.get("input_sha256", {}).get("reviewed_unreachable") != sha256(UNREACHABLE_PATH)
            or manifest.get("reviewed_unreachable", {}).get("records") != list(records.values())):
        raise ValueError("Reviewed unreachable evidence provenance mismatch")
    protected = regional | origins | companies | reviewed
    candidates = {ipaddress.ip_network(prefix, strict=True) for prefix in records}
    mask = set()
    for version in (4, 6):
        remaining = builder.subtract(builder.intervals(candidates, version), builder.intervals(protected, version))
        mask.update(builder.networks_from_intervals(remaining, version))
    if manifest["reviewed_unreachable"].get("effective_cidrs") != len(mask):
        raise ValueError("Reviewed unreachable effective mask mismatch")
    for version in (4, 6):
        if builder.intersect(builder.intervals(mask, version), builder.intervals(protected, version)):
            raise ValueError("Reviewed unreachable mask intersects protected core")
    return mask


def verify_ipv6_admission_effect(ru, admitted, private, effective, regional, reviewed):
    """Check final IPv6 address space and measure removal against the no-IPv6-rule baseline."""
    def iv(networks):
        return builder.intervals(networks, 6)
    pre = builder.subtract(iv(admitted), iv(private))
    before = builder.subtract(builder.subtract(pre, iv(effective)), iv(regional))
    after = builder.subtract(before, iv(reviewed))
    if iv(ru) != after:
        raise ValueError("Reviewed IPv6 admission changed DIRECT outside the expected exact output")
    return builder.interval_size(builder.subtract(before, after))


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
    # Reconstruct v41 DIRECT service masks from the pinned routing feeds.
    # The HXEHEX diagnostic input is hash-checked, not used for admission.
    class Inputs: pass
    feeds = Inputs()
    feeds.kyoresuas_v4 = args.kyoresuas_v4
    feeds.kyoresuas_v6 = args.kyoresuas_v6
    feeds.kyoresuas_services = args.kyoresuas_services
    feeds.w1zardz = args.w1zardz
    feeds.escapingworm = args.escapingworm
    telegram = read_telegram_feed(args.telegram_feed)
    service_sources, source_stats, _ = builder.load_service_inputs(feeds)
    rir_resources, _ = builder.parse_rir_tsv(args.rir)
    regional_resources = builder.union_networks(*rir_resources.values())
    base = builder.parse_geoip_dat(args.base)
    if set(base) != {"RU", "PRIVATE"}:
        raise ValueError("Expected v37 base categories RU and PRIVATE")
    hydra_sources = builder.parse_hydra_direct_whitelist(args.hydra)
    hydra_routes = hydra_sources["hydra-direct"] | hydra_sources["hydra-whitelist"]
    reviewed = set(builder.parse_reviewed_operator_prefixes(args.reviewed_operator_prefixes))
    service_exact, service_resolver = builder.build_service_protection_masks(
        rir_resources, service_sources,
        w1zardz_literal_hosts=builder.original_w1zardz_hosts(args.w1zardz, service_sources["w1zardz-service-direct"]),
    )
    if company_core & shared or company_core | shared != company_all:
        raise ValueError("Company core/shared masks are not a disjoint exact partition")
    if any(builder.intervals(blocked_union, version) != builder.intervals(blocked_exact | blocked_resolved, version) for version in (4, 6)):
        raise ValueError("Approved blocked address-space union differs from exact + resolver sidecars")

    effective, resolved_only = builder.class_aware_effective_block_set(
        blocked_exact, blocked_resolved, company_core, shared, regional_only | regional_resources, service_exact, service_resolver,
        non_exempt=telegram, reviewed_operator_prefixes=reviewed,
    )
    output_blocked = builder.parse_cidr_file(args.effective_blocked)[0]
    if output_blocked != effective:
        raise ValueError("Published v41 effective block output differs from the class-aware policy calculation")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    regional_admission = builder.parse_regional_admission_exclusions(args.regional_admission_exclusions)
    ipv6_admission = verify_reviewed_ipv6_admission_manifest(args.reviewed_ipv6_admission_exclusions, manifest)
    cdn = cdn_networks(verify_cdn_manifest(manifest))
    unreachable = verify_unreachable_manifest(manifest, regional_resources, regional_all, company_all, reviewed)
    geography = set(regional_admission) | set(ipv6_admission)
    exemptions = hydra_routes | cdn
    foreign = builder.subtract_networks(geography, exemptions)
    admission = foreign | unreachable
    builder.assert_regional_admission_disjoint(decoded["RU"], admission)
    builder.assert_reviewed_operator_coverage(decoded["RU"], decoded["PRIVATE"], blocked_exact | telegram, admission, reviewed)
    for version in (4, 6):
        ru_iv = builder.intervals(decoded["RU"], version)
        private_iv = builder.intervals(decoded["PRIVATE"], version)
        blocked_iv = builder.intervals(output_blocked, version)
        exact_iv = builder.intervals(blocked_exact | telegram, version)
        admission_iv = builder.intervals(admission, version)
        core_iv = builder.intervals(company_core, version)
        shared_iv = builder.intervals(shared, version)
        regional_iv = builder.intervals(regional_only | regional_resources, version)
        service_resolver_iv = builder.intervals(service_resolver, version)
        if builder.intersect(ru_iv, private_iv):
            raise ValueError(f"RU intersects PRIVATE in IPv{version}")
        if builder.intersect(ru_iv, blocked_iv):
            raise ValueError(f"RU intersects effective blocked set in IPv{version}")

        core_expected = builder.subtract(core_iv, private_iv)
        core_missing = builder.subtract(builder.subtract(builder.subtract(core_expected, exact_iv), admission_iv), ru_iv)
        if core_missing:
            raise ValueError(f"CORE_CORPORATE prefix coverage lost in IPv{version}")

        shared_expected = builder.subtract(shared_iv, private_iv)
        shared_expected = builder.subtract(shared_expected, exact_iv)
        shared_missing = builder.subtract(builder.subtract(shared_expected, admission_iv), ru_iv)
        if shared_missing:
            raise ValueError(f"SHARED_INFRA resolver-only protection coverage lost in IPv{version}")
        regional_expected = builder.subtract(regional_iv, private_iv)
        regional_expected = builder.subtract(regional_expected, exact_iv)
        if builder.subtract(builder.subtract(regional_expected, admission_iv), ru_iv):
            raise ValueError(f"RIR RU+BY+KZ selected origin resolver-only protection lost in IPv{version}")
        service_expected = builder.subtract(service_resolver_iv, private_iv)
        service_expected = builder.subtract(service_expected, exact_iv)
        if builder.subtract(builder.subtract(service_expected, admission_iv), ru_iv):
            raise ValueError(f"Verified RU service protection lost in IPv{version}")

        # A shared provider may overlap an exact/legacy hard block, but no
        # resolver-only candidate may remain blocked inside a shared prefix.
        blocked_shared = builder.intersect(blocked_iv, shared_iv)
        allowed_shared_hard = builder.intersect(blocked_shared, exact_iv)
        if builder.subtract(blocked_shared, allowed_shared_hard):
            raise ValueError(f"Effective block intersects SHARED_INFRA outside exact/legacy hard blocks in IPv{version}")

    # Recompute expected coverage from both explicit Hydra categories.
    expected_hydra = builder.subtract_networks(hydra_routes, decoded["PRIVATE"], output_blocked | admission)
    for version in (4, 6):
        if builder.subtract(builder.intervals(expected_hydra, version), builder.intervals(decoded["RU"], version)):
            raise ValueError(f"Hydra DIRECT/WHITELIST IPv{version} eligible coverage missing")

    hxehex, hxehex_stats, _ = builder.load_hxehex_diagnostics(args.hxehex_ip)
    excluded = builder.read_w1zardz_exclusions(builder.W1ZARDZ_EXCLUSIONS)
    independently_admitted = builder.union_networks(
        base["RU"], regional_resources, regional_all, company_all, reviewed,
        *service_sources.values(), hydra_routes, cdn,
    )
    assert_hxehex_diagnostic_only(decoded["RU"], independently_admitted, hxehex)
    if builder.intersect(builder.intervals(excluded, 4),
                         builder.intervals(service_sources["w1zardz-service-direct"], 4)):
        raise ValueError("Excluded gaming address still present in W1ZARDZ admission")
    assert_no_w1zardz_only_gaming_routes(decoded["RU"], independently_admitted, excluded)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if (manifest.get("input_sha256", {}).get("w1zardz_direct") != sha256(args.w1zardz)
            or manifest.get("input_sha256", {}).get("w1zardz_gaming_exclusions") != sha256(builder.W1ZARDZ_EXCLUSIONS)
            or manifest.get("service_sources", {}).get("w1zardz-service-direct") != source_stats["w1zardz-service-direct"]):
        raise ValueError("W1ZARDZ source/exclusion provenance mismatch")
    for version in (4, 6):
        expected = builder.subtract(builder.intervals(independently_admitted, version), builder.intervals(decoded["PRIVATE"], version))
        expected = builder.subtract(expected, builder.intervals(output_blocked | admission, version))
        if expected != builder.intervals(decoded["RU"], version):
            raise ValueError(f"DIRECT IPv{version} differs from exact reachability policy")
    if (manifest.get("regional_admission_exclusions", {}).get("role") != ROLE
            or manifest.get("reviewed_ipv6_admission_exclusions", {}).get("role") != ROLE):
        raise ValueError("Missing exact foreign admission policy")
    geography_counts = {}
    for version in (4, 6):
        available = builder.subtract(builder.intervals(independently_admitted, version), builder.intervals(decoded["PRIVATE"], version))
        available = builder.subtract(available, builder.intervals(output_blocked, version))
        clean = builder.subtract(available, builder.intervals(unreachable, version))
        geography_counts[f"ipv{version}"] = builder.interval_size(
            builder.intersect(clean, builder.intervals(foreign, version)))
        without_geography = builder.subtract(available, builder.intervals(foreign, version))
        removed = builder.interval_size(builder.intersect(without_geography, builder.intervals(unreachable, version)))
        if manifest["reviewed_unreachable"]["removed_after_other_policy"][f"ipv{version}"] != removed:
            raise ValueError(f"Reviewed unreachable IPv{version} removal count mismatch")
    if (manifest["regional_admission_exclusions"].get("removed_after_block_policy")
            != {"ipv4": geography_counts["ipv4"], "ipv6": 0}
            or manifest["reviewed_ipv6_admission_exclusions"].get("removed_after_block_policy")
            != {"ipv6": geography_counts["ipv6"]}):
        raise ValueError("Foreign admission removal counts do not match the actual policy")

    hxehex_info = manifest.get("diagnostic_sources", {}).get("hxehex-mobile-hosts", {})
    if (manifest.get("base_v37_sha256") != sha256(args.base)
            or manifest.get("input_sha256", {}).get("hxehex_ipwhitelist") != sha256(args.hxehex_ip)
            or hxehex_info.get("role") != "diagnostic-only"
            or hxehex_info.get("status") != hxehex_stats["status"]
            or hxehex_info.get("unique_cidrs") != len(hxehex)
            or "hxehex-mobile-hosts" in manifest.get("service_sources", {})):
        raise ValueError("HXEHEX diagnostic source provenance mismatch")
    _, ipsum_stats = builder.parse_ipsum(args.ipsum)
    if (manifest.get("input_sha256", {}).get("antifilter_ipsum") != sha256(args.ipsum)
            or manifest.get("diagnostic_sources", {}).get("antifilter-ipsum") != {
                **ipsum_stats, "role": "diagnostic-only"
            }):
        raise ValueError("Antifilter ipsum diagnostic source provenance mismatch")
    if (manifest.get("input_sha256", {}).get("regional_admission_exclusions") != sha256(args.regional_admission_exclusions)
            or manifest.get("regional_admission_exclusions", {}).get("records") != list(regional_admission.values())):
        raise ValueError("Regional admission exclusion provenance mismatch")
    if manifest.get("input_sha256", {}).get("reviewed_operator_prefixes") != sha256(args.reviewed_operator_prefixes):
        raise ValueError("Reviewed operator prefix input SHA-256 mismatch")
    if manifest.get("input_sha256", {}).get("hydra_geoip") != sha256(args.hydra):
        raise ValueError("Hydra input SHA-256 mismatch")
    if manifest.get("hydra_routing_intent", {}).get("input_sha256") != sha256(args.hydra):
        raise ValueError("Hydra provenance SHA-256 mismatch")
    if (manifest.get("safety", {}).get("hydra_direct_whitelist_added_without_block_exemption") is not True
            or manifest["hydra_routing_intent"].get("whitelist_role") != "routing-intent"
            or manifest.get("service_sources", {}).get("operator-whitelist", {}).get("role")
            != "operator-routing-intent"
            or manifest["hydra_routing_intent"].get("combined_eligible_address_space")
            != builder.addr_counts(expected_hydra)):
        raise ValueError("DIRECT/WHITELIST policy provenance mismatch")
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
        raise ValueError("Manifest selected regional origin SHA-256 mismatch")

    if manifest.get("telegram_official") != {"cidrs": len(telegram), "input_sha256": sha256(args.telegram_feed)}:
        raise ValueError("Manifest official Telegram snapshot mismatch")

    safety = manifest.get("safety", {})
    required_flags = {
        "private_precedence_applied": True,
        "official_telegram_precedes_all_direct_exceptions": True,
        "confirmed_ip_subnet_precedes_all_direct_exceptions": True,
        "shared_infrastructure_prefixes_exempt_from_resolver_layer_only": True,
        "rkn_exact_ip_and_subnet_blocks_apply_to_shared_infrastructure": True,
        "legacy_v38_reclassification_preserves_approved_union": True,
        "rir_rukzby_selected_origin_resolver_protected": True,
        "all_direct_protection_masks_are_resolver_only": True,
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
        "Regional registration alone does not imply corporate ownership",
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
        "resolver_only_prefixes": len(resolved_only),
        "company_prefixes": len(company_all),
        "core_company_prefixes": len(company_core),
        "shared_infrastructure_prefixes": len(shared),
        "regional_additional_origin_prefixes": len(regional_only),
        "verified_service_exact_hosts": len(service_exact),
        "verified_service_resolver_prefixes": len(service_resolver),
        "hydra_direct_prefixes": len(hydra_sources["hydra-direct"]),
        "hydra_whitelist_prefixes": len(hydra_sources["hydra-whitelist"]),
        "status": "VALID",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report

def assert_no_w1zardz_only_gaming_routes(ru, independently_admitted, excluded):
    overlap = builder.intersect(builder.intervals(ru, 4), builder.intervals(excluded, 4))
    if builder.subtract(overlap, builder.intervals(independently_admitted, 4)):
        raise ValueError("W1ZARDZ-only gaming address still present in IPv4 DIRECT")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "geoip", "base", "hydra", "blocked_union", "blocked_exact", "blocked_resolved",
        "company_all", "company_core", "company_shared", "regional_origin_prefixes",
        "kyoresuas_v4", "kyoresuas_v6", "kyoresuas_services", "w1zardz",
        "hxehex_ip", "escapingworm", "effective_blocked", "ipsum",
        "manifest", "quality", "rir", "regional_admission_exclusions", "reviewed_operator_prefixes",
        "reviewed_ipv6_admission_exclusions",
    ):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--telegram-feed", type=Path, default=PINNED_FEED)
    args = parser.parse_args()
    try:
        validate(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
