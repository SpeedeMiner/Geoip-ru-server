#!/usr/bin/env python3
"""Join RIR residual candidates to exact origins in the verified ipverse snapshot.

This is an audit-only exact-NLRI join. It deliberately does not infer origins
from covering or more-specific routes, and a missing exact route in the rolling
90-day dataset is never interpreted as route withdrawal or unroutability.
"""
from __future__ import annotations

import argparse
import csv
import ipaddress
import sys
from pathlib import Path

from build_company_prefix_review import read_global_bgp_origins


class EvidenceError(ValueError):
    """Invalid input or inconsistent exact-origin evidence."""


def read_tsv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise EvidenceError(f"cannot read TSV {path}: {exc}") from exc
    if not rows:
        raise EvidenceError(f"TSV has no data rows: {path}")
    return rows


def build_evidence(args: argparse.Namespace) -> dict[str, int]:
    residual_rows = read_tsv(args.residual)
    inventory_rows = read_tsv(args.inventory)
    required_residual = {
        "PREFIX", "FAMILY", "PREFIX_ADDRESSES",
        "UNEXPLAINED_OUTSIDE_RU_PRIVATE_BLOCKED_ADDRESSES", "STATUS",
    }
    required_inventory = {
        "PREFIX", "IN_GLOBAL_BGP_90D_OBSERVATIONS",
        "IN_SELECTED_RIR_OR_COMPANY_ORIGIN_BGP",
        "IN_ACCEPTED_ADDITIONAL_GEOIP_FEEDS",
    }
    if not required_residual.issubset(residual_rows[0]):
        raise EvidenceError(f"RIR residual TSV missing columns: {sorted(required_residual-set(residual_rows[0]))}")
    if not required_inventory.issubset(inventory_rows[0]):
        raise EvidenceError(f"canonical inventory TSV missing columns: {sorted(required_inventory-set(inventory_rows[0]))}")

    inventory_by_prefix: dict[str, dict[str, str]] = {}
    for row in inventory_rows:
        prefix = ipaddress.ip_network(row["PREFIX"], strict=True).with_prefixlen
        if prefix in inventory_by_prefix:
            raise EvidenceError(f"duplicate exact prefix in canonical inventory: {prefix}")
        inventory_by_prefix[prefix] = row

    targets: set[str] = set()
    normalized_rows: dict[str, dict[str, str]] = {}
    for row in residual_rows:
        prefix = ipaddress.ip_network(row["PREFIX"], strict=True).with_prefixlen
        if prefix in targets:
            raise EvidenceError(f"duplicate exact RIR residual prefix: {prefix}")
        if row["STATUS"] != "REVIEW":
            raise EvidenceError(f"RIR residual input contains non-REVIEW row: {prefix}")
        network = ipaddress.ip_network(prefix)
        if row["FAMILY"] != f"IPv{network.version}" or int(row["PREFIX_ADDRESSES"]) != network.num_addresses:
            raise EvidenceError(f"RIR residual metadata mismatch: {prefix}")
        if int(row["UNEXPLAINED_OUTSIDE_RU_PRIVATE_BLOCKED_ADDRESSES"]) <= 0:
            raise EvidenceError(f"non-residual prefix found in residual queue: {prefix}")
        if prefix not in inventory_by_prefix:
            raise EvidenceError(f"RIR residual prefix missing from canonical inventory: {prefix}")
        targets.add(prefix)
        normalized_rows[prefix] = row

    # Every absent exact prefix is explicitly allowed here. The helper still
    # rejects malformed archives and malformed aggregated.json members.
    origins, countries = read_global_bgp_origins(
        args.bgp_archive,
        targets,
        allowed_missing_static=targets,
    )

    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "PREFIX", "FAMILY", "PREFIX_ADDRESSES",
        "UNEXPLAINED_OUTSIDE_RU_PRIVATE_BLOCKED_ADDRESSES",
        "GLOBAL_BGP_90D_EXACT_OBSERVATION",
        "GLOBAL_BGP_90D_EXACT_ORIGIN_ASNS",
        "GLOBAL_BGP_90D_EXACT_ORIGIN_COUNTRY_CODES",
        "GLOBAL_BGP_90D_EXACT_MOAS",
        "IN_SELECTED_ORIGIN_BGP_EXACT",
        "IN_ADDITIONAL_GEOIP_FEEDS_EXACT",
        "STATUS", "EVIDENCE_LIMITATION",
    ]
    observed = 0
    moas = 0
    selected_exact = 0
    additional_exact = 0
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for prefix in sorted(targets, key=lambda value: (
            ipaddress.ip_network(value).version,
            int(ipaddress.ip_network(value).network_address),
            ipaddress.ip_network(value).prefixlen,
        )):
            row = normalized_rows[prefix]
            inv = inventory_by_prefix[prefix]
            exact_origins = sorted(origins.get(prefix, set()))
            exact_countries = countries.get(prefix, {})
            seen = bool(exact_origins)
            observed += int(seen)
            moas += int(len(exact_origins) > 1)
            selected = inv["IN_SELECTED_RIR_OR_COMPANY_ORIGIN_BGP"] == "yes"
            additional = inv["IN_ACCEPTED_ADDITIONAL_GEOIP_FEEDS"] == "yes"
            selected_exact += int(selected)
            additional_exact += int(additional)
            if (inv["IN_GLOBAL_BGP_90D_OBSERVATIONS"] == "yes") != seen:
                raise EvidenceError(f"global exact-NLRI flag disagrees with origin parser for {prefix}")
            writer.writerow({
                "PREFIX": prefix,
                "FAMILY": row["FAMILY"],
                "PREFIX_ADDRESSES": row["PREFIX_ADDRESSES"],
                "UNEXPLAINED_OUTSIDE_RU_PRIVATE_BLOCKED_ADDRESSES": row["UNEXPLAINED_OUTSIDE_RU_PRIVATE_BLOCKED_ADDRESSES"],
                "GLOBAL_BGP_90D_EXACT_OBSERVATION": "OBSERVED" if seen else "NOT_OBSERVED_IN_90D_SNAPSHOT",
                "GLOBAL_BGP_90D_EXACT_ORIGIN_ASNS": ",".join(f"AS{asn}" for asn in exact_origins),
                "GLOBAL_BGP_90D_EXACT_ORIGIN_COUNTRY_CODES": ",".join(
                    f"AS{asn}={exact_countries.get(asn, 'UNKNOWN')}" for asn in exact_origins
                ),
                "GLOBAL_BGP_90D_EXACT_MOAS": "yes" if len(exact_origins) > 1 else "no",
                "IN_SELECTED_ORIGIN_BGP_EXACT": "yes" if selected else "no",
                "IN_ADDITIONAL_GEOIP_FEEDS_EXACT": "yes" if additional else "no",
                "STATUS": "REVIEW",
                "EVIDENCE_LIMITATION": (
                    "Exact NLRI only; countryCode is publisher metadata, not geolocation. "
                    "A missing exact route in this rolling 90-day snapshot is not proof of route withdrawal; "
                    "covering/more-specific NLRI are not projected onto this prefix."
                ),
            })

    stats = [
        "RIR residual exact-origin evidence (review only)",
        f"RIR residual exact prefixes: {len(targets)}",
        f"Exact prefixes observed in ipverse 90-day snapshot: {observed}",
        f"Exact prefixes not observed in ipverse 90-day snapshot: {len(targets)-observed}",
        f"Exact MOAS prefixes in ipverse 90-day snapshot: {moas}",
        f"Exact prefixes present in selected-origin input: {selected_exact}",
        f"Exact prefixes present in accepted additional GeoIP provenance: {additional_exact}",
        "All rows remain STATUS=REVIEW.",
        "Origin ASN/countryCode values are exact-NLRI observations in the pinned rolling 90-day archive.",
        "CountryCode is not proof of resource ownership or physical hosting location.",
        "No exact observation is not evidence of route withdrawal, unroutability, or missing BGP coverage outside this snapshot.",
        "Covering and more-specific routes are not used as exact-prefix origin evidence.",
    ]
    args.stats.write_text("\n".join(stats) + "\n", encoding="utf-8")
    return {
        "prefixes": len(targets),
        "exact_observed": observed,
        "exact_not_observed": len(targets) - observed,
        "exact_moas": moas,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--residual", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--bgp-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_evidence(args)
    except (EvidenceError, OSError, csv.Error, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"Built exact BGP-origin evidence for {result['prefixes']} RIR residual prefixes: "
        f"observed={result['exact_observed']}, not_observed={result['exact_not_observed']}, "
        f"MOAS={result['exact_moas']}; all REVIEW"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
