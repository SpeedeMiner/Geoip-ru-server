#!/usr/bin/env python3
"""Join archived invalid RPKI observations to the dated exact-NLRI review evidence."""
from __future__ import annotations
import argparse
import csv
import ipaddress
import re
from collections import Counter, defaultdict
from pathlib import Path

OUTPUT_FIELDS = (
    "PREFIX", "ARCHIVED_BGP_ORIGIN_ASNS", "ARCHIVED_INVALID_RPKI_ORIGINS",
    "ARCHIVED_RPKI_QUERY_STATUS", "EXTERNAL_NLRI_SCOPE_RELATION",
    "EXTERNAL_OBSERVED_NLRI", "EXTERNAL_EXACT_ORIGIN_ASNS",
    "EXTERNAL_EXACT_RPKI_STATUS", "EXTERNAL_CHILD_ROUTE_NOTES",
    "RECONCILIATION_CLASS", "ASSESSMENT", "REQUIRED_NEXT_ACTION",
    "SOURCE_URLS", "STATUS",
)
ALLOWED_CLASSES = {
    "EXACT_ORIGIN_SET_CHANGED",
    "EXACT_MOAS_RPKI_STATUS_CHANGED",
    "EXACT_MOAS_INVALID_ORIGIN_REMAINS_UNCONFIRMED",
    "MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT",
}
ASN_RE = re.compile(r"AS[0-9]+\Z")
UNSEEDED_CLASS = "UNSEEDED_CURRENT_RPKI_INVALID_NEEDS_SPOT_CHECK"
UNSEEDED_FIELDS = (
    "PREFIX", "ORIGIN_ASN", "RPKI_STATUS", "RPKI_URL", "RECONCILIATION_CLASS",
    "REQUIRED_NEXT_ACTION", "STATUS",
)

def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(
            (line for line in stream if not line.startswith("#")), delimiter="\t"
        ))
    if not rows:
        raise ValueError(f"empty TSV: {path}")
    return rows

def unique(rows: list[dict[str, str]], field: str, label: str) -> dict[str, dict[str, str]]:
    result = {}
    for row in rows:
        key = row.get(field, "").strip()
        if not key or key in result:
            raise ValueError(f"empty or duplicate {label}: {key!r}")
        result[key] = row
    return result

def split_set(value: str) -> set[str]:
    return {item.strip() for item in value.replace(",", "|").split("|") if item.strip()}

def build_reconciliation(evidence_dir: Path, seed_path: Path, output_path: Path,
                         stats_path: Path, expected_count: int | None = 19, *,
                         unseeded_path: Path | None = None) -> dict[str, object]:
    triage = unique(read_tsv(evidence_dir / "priority_prefix_triage.tsv"), "PREFIX", "triage prefix")
    worklist = unique(read_tsv(evidence_dir / "priority_prefix_review_worklist.tsv"), "PREFIX", "worklist prefix")
    spots = unique(read_tsv(evidence_dir / "priority_prefix_external_spot_checks_v37.tsv"), "PREFIX", "spot-check prefix")
    rpki_rows = read_tsv(evidence_dir / "rpki_by_origin.tsv")
    rpki = {}
    for row in rpki_rows:
        key = (row.get("PREFIX", "").strip(), row.get("ORIGIN_ASN", "").strip())
        if not all(key) or key in rpki:
            raise ValueError(f"empty or duplicate RPKI prefix/origin pair: {key}")
        rpki[key] = row

    seed_rows = read_tsv(seed_path)
    seed = unique(seed_rows, "PREFIX", "reconciliation seed prefix")
    invalid_prefixes = {
        prefix for prefix, row in triage.items()
        if "RPKI_INVALID_ASN" in split_set(row.get("TRIAGE_FLAGS", ""))
    }
    if expected_count is not None and len(seed) != expected_count:
        raise ValueError(f"archived invalid seed scope changed: expected {expected_count}, got {len(seed)}")
    if not set(seed) <= invalid_prefixes:
        raise ValueError(
            f"curated reconciliation inventory differs from archive; "
            f"historical prefixes missing from invalid triage={sorted(set(seed)-invalid_prefixes)}"
        )

    current_by_prefix = defaultdict(set)
    for (prefix, asn), row in rpki.items():
        if row.get("QUERY_STATUS") == "OK" and row.get("RPKI_STATUS") == "invalid_asn":
            current_by_prefix[prefix].add(asn)
    if set(current_by_prefix) != invalid_prefixes:
        raise ValueError("archived invalid RPKI pair missing or changed, or triage omits a current invalid prefix")

    historical_by_prefix = {}
    for prefix, row in seed.items():
        historical = split_set(row.get("ARCHIVED_INVALID_RPKI_ORIGINS", ""))
        if not historical or any(not ASN_RE.fullmatch(asn) for asn in historical):
            raise ValueError(f"missing or invalid archived seed origin for {prefix}")
        if not historical <= current_by_prefix[prefix]:
            raise ValueError(
                f"archived invalid RPKI pair missing or changed for {prefix}: "
                f"{sorted(historical-current_by_prefix[prefix])}"
            )
        historical_by_prefix[prefix] = historical

    def prefix_key(prefix):
        net = ipaddress.ip_network(prefix, strict=True)
        return net.version, int(net.network_address), net.prefixlen

    unseeded = []
    for prefix in sorted(invalid_prefixes, key=prefix_key):
        tri = triage[prefix]
        wl = worklist.get(prefix)
        if wl is None or tri.get("STATUS") != "REVIEW" or wl.get("STATUS") != "REVIEW":
            raise ValueError(f"non-REVIEW or missing source row for {prefix}")
        invalid_asns = split_set(tri.get("RPKI_INVALID_ORIGINS", ""))
        origins = split_set(tri.get("GLOBAL_BGP_ORIGIN_ASNS", ""))
        if invalid_asns != current_by_prefix[prefix] or not invalid_asns <= origins:
            raise ValueError(f"invalid-origin set does not match RPKI and observed BGP for {prefix}")
        if any(not ASN_RE.fullmatch(asn) for asn in origins):
            raise ValueError(f"invalid ASN token for {prefix}")
        for asn in sorted(invalid_asns - historical_by_prefix.get(prefix, set())):
            url = rpki[(prefix, asn)].get("RPKI_URL", "").strip()
            if not url.startswith("https://"):
                raise ValueError(f"missing HTTPS RPKI evidence for {prefix} {asn}")
            unseeded.append({
                "PREFIX": prefix,
                "ORIGIN_ASN": asn,
                "RPKI_STATUS": "invalid_asn",
                "RPKI_URL": url,
                "RECONCILIATION_CLASS": UNSEEDED_CLASS,
                "REQUIRED_NEXT_ACTION": "Check exact NLRI and origin against a fresh full RIB and current VRPs.",
                "STATUS": "REVIEW",
            })

    output = []
    classes = Counter()
    for prefix in sorted(seed, key=prefix_key):
        wl = worklist[prefix]
        invalid_asns = historical_by_prefix[prefix]
        origins = split_set(triage[prefix].get("GLOBAL_BGP_ORIGIN_ASNS", ""))

        spot = spots.get(prefix)
        if spot is None or wl.get("EXTERNAL_SPOT_CHECK_STATUS") != "CHECKED_2026-11-10":
            raise ValueError(f"external spot-check row is missing for {prefix}")
        relation = wl.get("EXTERNAL_SPOT_CHECK_SCOPE_RELATION", "")
        if not relation or relation != spot_relation(prefix, spot):
            raise ValueError(f"NLRI scope relation mismatch between worklist and source spot-check for {prefix}")
        seed_row = seed[prefix]
        exact_origins = split_set(seed_row.get("EXTERNAL_EXACT_ORIGIN_ASNS", ""))
        exact_rpki = seed_row.get("EXTERNAL_EXACT_RPKI_STATUS", "").strip()
        assessment_class = seed_row.get("RECONCILIATION_CLASS", "").strip()
        if assessment_class not in ALLOWED_CLASSES:
            raise ValueError(f"unsupported reconciliation class for {prefix}: {assessment_class}")
        if relation == "MORE_SPECIFIC_ONLY" and exact_origins:
            raise ValueError(f"more-specific-only evidence cannot assert exact origins for {prefix}")
        if relation != "MORE_SPECIFIC_ONLY" and not exact_origins:
            raise ValueError(f"exact-scope evidence requires an explicit exact-origin set for {prefix}")
        for asn in exact_origins:
            if not ASN_RE.fullmatch(asn):
                raise ValueError(f"invalid external exact-origin ASN for {prefix}: {asn}")
        source_urls = [x.strip() for x in spot.get("SOURCE_URLS", "").split("|") if x.strip()]
        if not source_urls or any(not url.startswith("https://") for url in source_urls):
            raise ValueError(f"missing HTTPS sources for {prefix}")
        assessment = seed_row.get("ASSESSMENT", "").strip()
        action = seed_row.get("REQUIRED_NEXT_ACTION", "").strip()
        if not assessment or not action:
            raise ValueError(f"missing analyst assessment/action for {prefix}")

        # Preserve the original invalid pair statuses; do not infer current status from a
        # related more-specific route or from another origin's ROA.
        archived_query = ";".join(
            f"{asn}:{rpki[(prefix, asn)]['RPKI_STATUS']}"
            for asn in sorted(invalid_asns)
        )
        output.append({
            "PREFIX": prefix,
            "ARCHIVED_BGP_ORIGIN_ASNS": "|".join(sorted(origins)),
            "ARCHIVED_INVALID_RPKI_ORIGINS": "|".join(sorted(invalid_asns)),
            "ARCHIVED_RPKI_QUERY_STATUS": archived_query,
            "EXTERNAL_NLRI_SCOPE_RELATION": relation,
            "EXTERNAL_OBSERVED_NLRI": spot.get("OBSERVED_PREFIXES", ""),
            "EXTERNAL_EXACT_ORIGIN_ASNS": "|".join(sorted(exact_origins)),
            "EXTERNAL_EXACT_RPKI_STATUS": exact_rpki,
            "EXTERNAL_CHILD_ROUTE_NOTES": spot.get("SUMMARY", ""),
            "RECONCILIATION_CLASS": assessment_class,
            "ASSESSMENT": assessment,
            "REQUIRED_NEXT_ACTION": action,
            "SOURCE_URLS": spot.get("SOURCE_URLS", ""),
            "STATUS": "REVIEW",
        })
        classes[assessment_class] += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("# Reconciliation of the pinned 90-day BGP/RPKI archive against external exact-NLRI spot checks.\n")
        stream.write("# External observations are asynchronous and not a synchronized current global RIB/VRP snapshot.\n")
        stream.write("# All rows remain REVIEW; no DIRECT, ownership or allowlist decision is made.\n")
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)

    if unseeded_path is None:
        unseeded_path = output_path.with_name("unseeded_rpki_invalid_review.tsv")
    unseeded_path.parent.mkdir(parents=True, exist_ok=True)
    with unseeded_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=UNSEEDED_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(unseeded)

    stats = [
        "Artifact: v37 archived-invalid RPKI exact-NLRI reconciliation",
        f"Archived invalid prefixes: {len(output)}",
        f"Unseeded invalid prefix/origin pairs for REVIEW: {len(unseeded)}",
        f"Rows with exact-scope external observations: {sum(r['EXTERNAL_NLRI_SCOPE_RELATION'] != 'MORE_SPECIFIC_ONLY' for r in output)}",
        f"Rows with more-specific-only observations: {sum(r['EXTERNAL_NLRI_SCOPE_RELATION'] == 'MORE_SPECIFIC_ONLY' for r in output)}",
        "All rows: STATUS=REVIEW",
        "External observations are asynchronous and do not replace a synchronized full-RIB plus VRP refresh.",
        "A covering or more-specific route's origin/RPKI state is never projected onto the exact priority NLRI.",
        "No DIRECT prefix, company allowlist or production output is changed by this reconciliation.",
    ]
    stats.extend(f"Class {name}: {count}" for name, count in sorted(classes.items()))
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text("\n".join(stats) + "\n", encoding="utf-8")
    return {"rows": len(output), "classes": dict(classes), "unseeded_pairs": len(unseeded)}

def spot_relation(prefix: str, row: dict[str, str]) -> str:
    target = ipaddress.ip_network(prefix, strict=True)
    observed = [ipaddress.ip_network(x.strip(), strict=True)
                for x in row.get("OBSERVED_PREFIXES", "").split("|") if x.strip()]
    if not observed:
        raise ValueError(f"spot-check has no NLRI for {prefix}")
    relations = set()
    for network in observed:
        if network == target:
            relations.add("EXACT")
        elif network.subnet_of(target):
            relations.add("MORE_SPECIFIC")
        elif target.subnet_of(network):
            relations.add("COVERED_BY")
        else:
            raise ValueError(f"unrelated external NLRI for {prefix}: {network}")
    if relations == {"EXACT"}: return "EXACT_ONLY"
    if relations == {"MORE_SPECIFIC"}: return "MORE_SPECIFIC_ONLY"
    if relations == {"COVERED_BY"}: return "COVERED_BY_ONLY"
    if relations == {"EXACT", "MORE_SPECIFIC"}: return "EXACT_AND_MORE_SPECIFIC"
    if relations == {"EXACT", "COVERED_BY"}: return "EXACT_AND_COVERED_BY"
    return "MIXED_OVERLAPPING_SCOPE"

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--unseeded-output", type=Path)
    args = parser.parse_args()
    try:
        print(build_reconciliation(args.evidence_dir, args.seed, args.output, args.stats,
                                   unseeded_path=args.unseeded_output))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
