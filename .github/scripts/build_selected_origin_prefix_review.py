#!/usr/bin/env python3
"""Build a review-only queue for every selected regional/company BGP origin prefix.

This report is an audit artifact only. It does not approve, reject, add, or remove
any address from the current GeoIP DIRECT output. All rows are REVIEW until
prefix-level ownership/control and DIRECT suitability are separately established.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import ipaddress
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from build_company_prefix_review import (
    parse_selected_origins,
    _prefix_sort_key,
    _union_addresses,
    read_bgp_snapshot,
    read_company_manifest,
    read_company_registry,
    read_global_bgp_origins,
    _sha256_file,
)

HEADER = (
    "PREFIX", "FAMILY", "ADDRESS_COUNT",
    "SELECTED_ORIGIN_ASNS", "SELECTED_ORIGIN_LABELS",
    "COMPANY_ASNS", "COMPANY_GROUPS", "LEGAL_ENTITIES",
    "COMPANY_ASN_DETAILS_JSON", "REGIONAL_RIR_ORIGIN_ASNS",
    "INCLUSION_BASIS", "GLOBAL_BGP_ORIGIN_ASNS",
    "GLOBAL_BGP_ORIGIN_COUNTRY_CODES", "GLOBAL_BGP_MOAS", "GLOBAL_BGP_OBSERVATION",
    "RPKI_STATUS", "IRR_STATUS", "STATUS",
    "CURRENT_PIPELINE_EVIDENCE", "REVIEW_REASON",
    "GENERATED_UTC", "BGP_SNAPSHOT_SHA256", "BGP_SNAPSHOT_URL",
)

REVIEW_REASON = (
    "This prefix is selected by the current regional/company ASN pipeline, but "
    "ASN registration/origin labels do not prove ownership or control of this "
    "exact resource, physical geography, or DIRECT suitability. Verify prefix "
    "level RDAP/RIR allocation, legal-entity relationship, RPKI/ROA, IRR, all "
    "origin ASNs, customer/tenant/CDN/hosting role, and the reason DIRECT is "
    "required before changing its status."
)


def _join(values: Iterable[object]) -> str:
    return ",".join(str(value) for value in sorted(values, key=lambda value: str(value)))


def build_review(
    selected_prefixes: Path,
    company_registry: Path,
    company_manifest: Path,
    input_provenance: Path,
    bgp_archive: Path,
    output: Path,
    stats: Path,
) -> tuple[int, int, int]:
    companies = read_company_registry(company_registry)
    company_metadata = read_company_manifest(company_manifest, companies)
    snapshot_sha, snapshot_url = read_bgp_snapshot(input_provenance, bgp_archive)
    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    input_hashes = {
        "company_registry": _sha256_file(company_registry),
        "company_manifest": _sha256_file(company_manifest),
        "selected_prefixes": _sha256_file(selected_prefixes),
        "input_provenance": _sha256_file(input_provenance),
    }

    records: dict[str, dict[str, object]] = {}
    try:
        lines = selected_prefixes.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read selected BGP prefix input {selected_prefixes}: {exc}") from exc

    for line_no, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        prefix_token, separator, comment = line.partition("#")
        if not separator:
            raise ValueError(f"{selected_prefixes}:{line_no}: missing origin annotation")
        try:
            network = ipaddress.ip_network(prefix_token.strip(), strict=True)
        except ValueError as exc:
            raise ValueError(
                f"{selected_prefixes}:{line_no}: invalid prefix {prefix_token.strip()!r}"
            ) from exc

        origins = parse_selected_origins(comment)
        if not origins:
            raise ValueError(
                f"{selected_prefixes}:{line_no}: selected prefix has no parsed origin ASN annotation"
            )

        key = network.with_prefixlen
        item = records.setdefault(key, {
            "network": network,
            "selected_origins": set(),
            "selected_labels": defaultdict(set),
            "company_asns": set(),
            "company_groups": set(),
            "entities": set(),
            "regional_origins": set(),
        })
        for asn, labels in origins:
            item["selected_origins"].add(asn)
            item["selected_labels"][asn].update(labels)
            if asn in companies:
                item["company_asns"].add(asn)
                item["company_groups"].add(companies[asn]["group"])
                item["entities"].add(companies[asn]["entity"])
            if "RIR-RU" in labels or "RIR-BY/KZ" in labels:
                item["regional_origins"].add(asn)

    if not records:
        raise ValueError("selected BGP prefix input contains no origin prefixes")

    # Validate the policy role before consulting the global BGP snapshot.
    # An unclassified selected-origin row is invalid input regardless of whether
    # that prefix happens to be present in the observational archive.
    for prefix, item in records.items():
        if not item["company_asns"] and not item["regional_origins"]:
            raise ValueError(
                f"selected prefix {prefix} has no company or regional RIR origin label"
            )

    target_prefixes = set(records)
    static_direct = {prefix for prefix, item in records.items()
                     if any("STATIC-DIRECT" in labels for labels in item["selected_labels"].values())}
    global_origins, global_countries = read_global_bgp_origins(
        bgp_archive, target_prefixes, allowed_missing_static=static_direct
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"# Generated UTC: {generated}\n")
        handle.write(f"# BGP source URL: {snapshot_url}\n")
        handle.write(f"# BGP source SHA256: {snapshot_sha}\n")
        handle.write(f"# Company ASN registry SHA256: {input_hashes['company_registry']}\n")
        handle.write(f"# Company ASN manifest SHA256: {input_hashes['company_manifest']}\n")
        handle.write(f"# Selected prefix input SHA256: {input_hashes['selected_prefixes']}\n")
        handle.write(f"# Input provenance SHA256: {input_hashes['input_provenance']}\n")
        handle.write("# RPKI and IRR were not queried; NOT_QUERIED is not a negative result.\n")
        handle.write("# Every selected prefix is REVIEW; this report does not alter GeoIP output.\n")
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)

        for prefix in sorted(records, key=_prefix_sort_key):
            item = records[prefix]
            network = item["network"]
            company_asns = item["company_asns"]
            regional_asns = item["regional_origins"]
            selected_asns = item["selected_origins"]
            origin_asns = global_origins[prefix]

            if company_asns and regional_asns:
                inclusion_basis = "REGIONAL_RIR_ASN+COMPANY_ASN"
            elif company_asns:
                inclusion_basis = "COMPANY_ASN_ONLY"
            elif regional_asns:
                inclusion_basis = "REGIONAL_RIR_ASN_ONLY"
            else:
                # The selected input should only contain one of the above policy
                # classes. Fail closed rather than silently auditing an unknown role.
                raise ValueError(
                    f"selected prefix {prefix} has no company or regional RIR origin label"
                )

            company_details = [
                {
                    "asn": f"AS{asn}",
                    "group": companies[asn]["group"],
                    "legal_entity": companies[asn]["entity"],
                    "ipverse_country_code": company_metadata[asn]["ipverse_country_code"],
                    "also_rir_ru": company_metadata[asn]["also_rir_ru"],
                    "also_rir_by_kz": company_metadata[asn]["also_rir_by_kz"],
                    "evidence_url": companies[asn]["evidence"],
                }
                for asn in sorted(company_asns)
            ]
            selected_labels = [
                f"AS{asn}[{'+'.join(sorted(item['selected_labels'][asn]))}]"
                for asn in sorted(selected_asns)
            ]

            writer.writerow([
                prefix,
                f"IPv{network.version}",
                network.num_addresses,
                _join(f"AS{asn}" for asn in selected_asns),
                ",".join(selected_labels),
                _join(f"AS{asn}" for asn in company_asns),
                _join(item["company_groups"]),
                _join(item["entities"]),
                json.dumps(
                    company_details,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                _join(f"AS{asn}" for asn in regional_asns),
                inclusion_basis,
                _join(f"AS{asn}" for asn in origin_asns),
                _join(
                    f"AS{asn}={global_countries[prefix][asn]}"
                    for asn in origin_asns
                ),
                "yes" if len(origin_asns) > 1 else "no",
                "OBSERVED" if origin_asns else "NOT_OBSERVED_STATIC_DIRECT_PIN",
                "NOT_QUERIED",
                "NOT_QUERIED",
                "REVIEW",
                "PRESENT_IN_SELECTED_BGP_INPUT",
                REVIEW_REASON,
                generated,
                snapshot_sha,
                snapshot_url,
            ])

    all_prefixes = set(records)
    company_prefixes = {
        prefix for prefix, item in records.items() if item["company_asns"]
    }
    regional_prefixes = {
        prefix for prefix, item in records.items() if item["regional_origins"]
    }
    company_only = {
        prefix for prefix, item in records.items()
        if item["company_asns"] and not item["regional_origins"]
    }
    regional_and_company = {
        prefix for prefix, item in records.items()
        if item["company_asns"] and item["regional_origins"]
    }
    regional_only = {
        prefix for prefix, item in records.items()
        if item["regional_origins"] and not item["company_asns"]
    }

    moas_count = sum(1 for prefix in all_prefixes if len(global_origins[prefix]) > 1)
    stats_lines = [
        f"Generated UTC: {generated}",
        f"BGP snapshot URL: {snapshot_url}",
        f"BGP snapshot SHA256: {snapshot_sha}",
        f"Company ASN registry SHA256: {input_hashes['company_registry']}",
        f"Company ASN manifest SHA256: {input_hashes['company_manifest']}",
        f"Selected prefix input SHA256: {input_hashes['selected_prefixes']}",
        f"Input provenance SHA256: {input_hashes['input_provenance']}",
        f"Unique selected regional/company origin prefixes: {len(all_prefixes)}",
        f"Unique IPv4 selected prefixes: {sum(1 for p in all_prefixes if ipaddress.ip_network(p).version == 4)}",
        f"Unique IPv6 selected prefixes: {sum(1 for p in all_prefixes if ipaddress.ip_network(p).version == 6)}",
        f"Selected IPv4 address-space union: {_union_addresses(all_prefixes, 4)}",
        f"Selected IPv6 address-space union: {_union_addresses(all_prefixes, 6)}",
        f"Prefixes with at least one company origin ASN: {len(company_prefixes)}",
        f"Prefixes with at least one regional RIR-RU/BY/KZ origin ASN: {len(regional_prefixes)}",
        f"Regional + company origin prefixes: {len(regional_and_company)}",
        f"Company-only origin prefixes: {len(company_only)}",
        f"Regional-only origin prefixes: {len(regional_only)}",
        f"Prefixes with multiple exact global BGP origin ASNs (MOAS): {moas_count}",
        f"Company-origin IPv4 address-space union: {_union_addresses(company_prefixes, 4)}",
        f"Company-origin IPv6 address-space union: {_union_addresses(company_prefixes, 6)}",
        f"Regional-origin IPv4 address-space union: {_union_addresses(regional_prefixes, 4)}",
        f"Regional-origin IPv6 address-space union: {_union_addresses(regional_prefixes, 6)}",
        f"Company-only IPv4 address-space union: {_union_addresses(company_only, 4)}",
        f"Company-only IPv6 address-space union: {_union_addresses(company_only, 6)}",
        f"Regional-only IPv4 address-space union: {_union_addresses(regional_only, 4)}",
        f"Regional-only IPv6 address-space union: {_union_addresses(regional_only, 6)}",
        "Review status: REVIEW for every row; no prefix is automatically approved or rejected.",
        "RPKI/ROA status: NOT_QUERIED; this is not a statement that a route is invalid or lacks a ROA.",
        "IRR status: NOT_QUERIED; this is not a statement that a route object is absent.",
        "Selected origins come from the current RIR/company ASN selection input; RIR flags are ASN registration labels, not prefix ownership.",
        "Global origin ASNs come from every aggregated.json file in the same ipverse snapshot; this 90-day observation is not a complete live RIB.",
        "STATIC-DIRECT pins absent from this snapshot remain in the review queue as NOT_OBSERVED_STATIC_DIRECT_PIN; this is not a route withdrawal.",
        "Exact MOAS means more than one origin ASN announced the exact same prefix in this snapshot; covering/more-specific routes are not counted as exact MOAS.",
        "Address-space totals are unions after CIDR collapse. Independent class totals can overlap and must not be added.",
        "This report is audit-only and does not alter geoip_RU.dat or the current DIRECT policy.",
    ]
    stats.write_text("\n".join(stats_lines) + "\n", encoding="utf-8")
    print("\n".join(stats_lines))
    return len(all_prefixes), len(company_prefixes), moas_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected-prefixes", type=Path, required=True)
    parser.add_argument("--company-asns", type=Path, required=True)
    parser.add_argument("--company-manifest", type=Path, required=True)
    parser.add_argument("--input-provenance", type=Path, required=True)
    parser.add_argument("--bgp-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_review(
            args.selected_prefixes,
            args.company_asns,
            args.company_manifest,
            args.input_provenance,
            args.bgp_archive,
            args.output,
            args.stats,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
