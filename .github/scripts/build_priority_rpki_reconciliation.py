#!/usr/bin/env python3
"""Join archived invalid RPKI observations to the dated exact-NLRI review evidence."""
from __future__ import annotations
import argparse
import csv
import ipaddress
import re
from datetime import date
from collections import Counter
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
                         stats_path: Path, expected_count: int | None = 19) -> dict[str, object]:
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
    if expected_count is not None and len(invalid_prefixes) != expected_count:
        raise ValueError(f"archived invalid-prefix scope changed: expected {expected_count}, got {len(invalid_prefixes)}")
    if set(seed) != invalid_prefixes:
        raise ValueError(
            f"curated reconciliation inventory differs from archive; "
            f"missing={sorted(invalid_prefixes-set(seed))}, extra={sorted(set(seed)-invalid_prefixes)}"
        )

    output = []
    classes = Counter()
    for prefix in sorted(seed, key=lambda p: (ipaddress.ip_network(p).version,
                                               int(ipaddress.ip_network(p).network_address),
                                               ipaddress.ip_network(p).prefixlen)):
        ipaddress.ip_network(prefix, strict=True)
        tri = triage[prefix]
        wl = worklist.get(prefix)
        if wl is None or tri.get("STATUS") != "REVIEW" or wl.get("STATUS") != "REVIEW":
            raise ValueError(f"non-REVIEW or missing source row for {prefix}")
        invalid_asns = split_set(tri.get("RPKI_INVALID_ORIGINS", ""))
        origins = split_set(tri.get("GLOBAL_BGP_ORIGIN_ASNS", ""))
        if not invalid_asns or not invalid_asns.issubset(origins):
            raise ValueError(f"invalid-origin set does not fit archived BGP origins for {prefix}")
        for asn in invalid_asns | origins:
            if not ASN_RE.fullmatch(asn):
                raise ValueError(f"invalid ASN token for {prefix}: {asn}")
        for asn in invalid_asns:
            obj = rpki.get((prefix, asn))
            if not obj or obj.get("RPKI_STATUS") != "invalid_asn" or obj.get("QUERY_STATUS") != "OK":
                raise ValueError(f"archived invalid RPKI pair missing or changed for {prefix} {asn}")

        spot = spots.get(prefix)
        spot_status = spot.get("STATUS", "").strip() if spot else ""
        worklist_status = wl.get("EXTERNAL_SPOT_CHECK_STATUS", "").strip()
        match = re.fullmatch(r"CHECKED_(\\d{4}-\\d{2}-\\d{2})", spot_status)
        if not match or worklist_status != spot_status:
            raise ValueError(f"external spot-check row is missing or date-mismatched for {prefix}")
        try:
            checked_date = date.fromisoformat(match.group(1))
        except ValueError as exc:
            raise ValueError(f"invalid spot-check calendar date for {prefix}") from exc
        if checked_date.isoformat() != match.group(1):
            raise ValueError(f"invalid spot-check calendar date for {prefix}")
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

    stats = [
        "Artifact: v37 archived-invalid RPKI exact-NLRI reconciliation",
        f"Archived invalid prefixes: {len(output)}",
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
    return {"rows": len(output), "classes": dict(classes)}

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
    args = parser.parse_args()
    try:
        print(build_reconciliation(args.evidence_dir, args.seed, args.output, args.stats))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
