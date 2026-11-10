#!/usr/bin/env python3
"""Build a review-only analyst worklist; never make DIRECT or ownership decisions."""
from __future__ import annotations
import argparse
import csv
import ipaddress
import re
from datetime import date
from collections import Counter
from pathlib import Path

EXPECTED = (56, 52, 4)
HEADER = (
    "REVIEW_ORDER", "REVIEW_PRIORITY", "PRIMARY_REVIEW_TRACK", "PREFIX", "FAMILY",
    "GLOBAL_BGP_ORIGIN_ASNS", "RPKI_INVALID_ORIGINS", "RPKI_UNKNOWN_ORIGINS",
    "IRR_EXACT_ORIGINS", "IRR_ORIGIN_ASNS_NOT_IN_BGP",
    "BGP_ORIGIN_ASNS_WITHOUT_EXACT_IRR", "RDAP_SAMPLE_CONSISTENCY",
    "RDAP_COUNTRIES", "TRIAGE_FLAGS", "REQUIRED_NEXT_ACTION",
    "EVIDENCE_FRESHNESS_WARNING", "EXTERNAL_SPOT_CHECK_STATUS",
    "EXTERNAL_SPOT_CHECK_PREFIXES", "EXTERNAL_SPOT_CHECK_SCOPE_RELATION", "EXTERNAL_SPOT_CHECK_SUMMARY",
    "EXTERNAL_SPOT_CHECK_SOURCE_URLS", "STATUS",
)

TRACKS = (
    (1, "P1", "RPKI_INVALID_ORIGIN_REVALIDATION", "RPKI_INVALID_ASN"),
    (2, "P1", "RPKI_QUERY_ERROR_RETRY", "RPKI_QUERY_ERROR"),
    (3, "P2", "RPKI_UNKNOWN_RECHECK", "RPKI_UNKNOWN"),
    (4, "P2", "IRR_BGP_ORIGIN_RECONCILIATION", "IRR_ORIGIN_SET_DIFFERS_FROM_BGP"),
    (5, "P2", "IRR_EXACT_OBJECT_SEARCH", "IRR_NO_EXACT_OBJECT"),
    (6, "P2", "IRR_QUERY_RETRY", "IRR_QUERY_ERROR"),
    (7, "P3", "RDAP_ALLOCATION_BOUNDARY_REVIEW", "RDAP_COUNTRY_MIXED"),
    (8, "P3", "RDAP_QUERY_RETRY", "RDAP_QUERY_ERROR"),
    (9, "P3", "RDAP_SUBALLOCATION_REVIEW", "RDAP_MULTIPLE_SAMPLE_OBJECTS"),
    (10, "P3", "COMPANY_ONLY_RESOURCE_ATTRIBUTION", "COMPANY_ONLY"),
    (11, "P4", "MOAS_ORIGIN_RELATIONSHIP_REVIEW", "MOAS"),
)

ACTIONS = {
    "RPKI_INVALID_ORIGIN_REVALIDATION": "Revalidate exact NLRI and each origin against current VRPs; check ROA maxLength and compare with a fresh full-RIB snapshot before interpreting the archived invalid flag.",
    "RPKI_QUERY_ERROR_RETRY": "Repeat exact prefix/origin validation independently; keep query failure separate from invalid or unknown status.",
    "RPKI_UNKNOWN_RECHECK": "Refresh current VRPs for every exact prefix/origin pair and distinguish no covering ROA from a validator/data gap.",
    "IRR_BGP_ORIGIN_RECONCILIATION": "Compare exact route/route6 origins with a fresh full-RIB origin set; inspect registry source, maintainer and object timestamps; separate stale objects from current announcements.",
    "IRR_EXACT_OBJECT_SEARCH": "Search the exact route/route6 object in additional IRR sources; absence in the eight queried RIPE/GRS sources is not global absence.",
    "IRR_QUERY_RETRY": "Repeat failed IRR source queries and preserve per-source errors; do not infer object absence.",
    "RDAP_ALLOCATION_BOUNDARY_REVIEW": "Resolve exact child-resource boundaries from RIR records; do not assign the whole prefix to one sampled entity or country.",
    "RDAP_QUERY_RETRY": "Retry failed RDAP samples and preserve partial-result status; do not infer the holder from incomplete samples.",
    "RDAP_SUBALLOCATION_REVIEW": "Expand RDAP lookups to allocation boundaries; preserve parent registration versus more-specific customer assignment.",
    "COMPANY_ONLY_RESOURCE_ATTRIBUTION": "Obtain direct evidence that the company/affiliate is entitled to originate or use this exact prefix; ASN registration, branding or transit alone is insufficient.",
    "MOAS_ORIGIN_RELATIONSHIP_REVIEW": "Review every exact-prefix origin independently; distinguish resource holder, origin, customer and transit roles. MOAS does not establish joint ownership.",
    "BASELINE_PREFIX_REVIEW": "Confirm exact-prefix resource assignment and all observed origins with current registry and routing evidence.",
}

def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader((line for line in stream if not line.startswith("#")), delimiter="\t"))
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

def build_worklist(evidence: Path, output: Path, stats_path: Path,
                   expected_scope: tuple[int, int, int] | None = EXPECTED) -> dict[str, object]:
    triage_rows = read_tsv(evidence / "priority_prefix_triage.tsv")
    triage = unique(triage_rows, "PREFIX", "triage prefix")
    spot_path = evidence / "priority_prefix_external_spot_checks_v37.tsv"
    spot_rows = read_tsv(spot_path) if spot_path.exists() else []
    spots = unique(spot_rows, "PREFIX", "external spot-check prefix")
    scope = (
        len(triage_rows),
        sum(r.get("GLOBAL_BGP_MOAS", "").lower() == "yes" for r in triage_rows),
        sum(r.get("INCLUSION_BASIS") == "COMPANY_ASN_ONLY" for r in triage_rows),
    )
    if expected_scope is not None and scope != expected_scope:
        raise ValueError(f"priority scope changed: expected {expected_scope}, got {scope}")
    extra = sorted(set(spots) - set(triage))
    if extra:
        raise ValueError(f"spot-check rows outside priority inventory: {extra}")

    for prefix, row in triage.items():
        net = ipaddress.ip_network(prefix, strict=True)
        if row.get("STATUS") != "REVIEW" or row.get("FAMILY") != f"IPv{net.version}":
            raise ValueError(f"invalid family or non-REVIEW triage row: {prefix}")
    spot_scope_relations: dict[str, str] = {}
    for prefix, row in spots.items():
        status = row.get("STATUS", "").strip()
        match = re.fullmatch(r"CHECKED_(\\d{4}-\\d{2}-\\d{2})", status)
        if not match or not row.get("SUMMARY", "").strip():
            raise ValueError(f"invalid or undated spot-check row: {prefix}")
        try:
            checked_date = date.fromisoformat(match.group(1))
        except ValueError as exc:
            raise ValueError(f"invalid or undated spot-check row: {prefix}") from exc
        if checked_date.isoformat() != match.group(1):
            raise ValueError(f"invalid or undated spot-check row: {prefix}")
        target = ipaddress.ip_network(prefix, strict=True)
        observed = [ipaddress.ip_network(x.strip(), strict=True)
                    for x in row.get("OBSERVED_PREFIXES", "").split("|") if x.strip()]
        urls = [x.strip() for x in row.get("SOURCE_URLS", "").split("|") if x.strip()]
        if not observed or not urls or any(not u.startswith("https://") for u in urls):
            raise ValueError(f"spot-check missing exact scope or HTTPS source: {prefix}")
        relations = set()
        for network in observed:
            if network == target:
                relations.add("EXACT")
            elif network.subnet_of(target):
                relations.add("MORE_SPECIFIC")
            elif target.subnet_of(network):
                relations.add("COVERED_BY")
            else:
                raise ValueError(f"spot-check NLRI is unrelated to target prefix: {prefix}")
        if relations == {"EXACT"}:
            relation = "EXACT_ONLY"
        elif relations == {"MORE_SPECIFIC"}:
            relation = "MORE_SPECIFIC_ONLY"
        elif relations == {"COVERED_BY"}:
            relation = "COVERED_BY_ONLY"
        elif relations == {"EXACT", "MORE_SPECIFIC"}:
            relation = "EXACT_AND_MORE_SPECIFIC"
        elif relations == {"EXACT", "COVERED_BY"}:
            relation = "EXACT_AND_COVERED_BY"
        else:
            relation = "MIXED_OVERLAPPING_SCOPE"
        spot_scope_relations[prefix] = relation

    def track(row):
        flags = {x.strip() for x in row.get("TRIAGE_FLAGS", "").split("|") if x.strip()}
        for order, priority, name, flag in TRACKS:
            if flag in flags:
                return order, priority, name
        return 12, "P4", "BASELINE_PREFIX_REVIEW"

    ordered = sorted(
        triage_rows,
        key=lambda r: (track(r)[0], ipaddress.ip_network(r["PREFIX"]).version,
                       int(ipaddress.ip_network(r["PREFIX"]).network_address),
                       ipaddress.ip_network(r["PREFIX"]).prefixlen),
    )
    result, priorities, tracks = [], Counter(), Counter()
    for row in ordered:
        prefix = row["PREFIX"]
        order, priority, name = track(row)
        spot = spots.get(prefix, {})
        result.append({
            "REVIEW_ORDER": str(order), "REVIEW_PRIORITY": priority,
            "PRIMARY_REVIEW_TRACK": name, "PREFIX": prefix, "FAMILY": row["FAMILY"],
            "GLOBAL_BGP_ORIGIN_ASNS": row.get("GLOBAL_BGP_ORIGIN_ASNS", ""),
            "RPKI_INVALID_ORIGINS": row.get("RPKI_INVALID_ORIGINS", ""),
            "RPKI_UNKNOWN_ORIGINS": row.get("RPKI_UNKNOWN_ORIGINS", ""),
            "IRR_EXACT_ORIGINS": row.get("IRR_EXACT_ORIGINS", ""),
            "IRR_ORIGIN_ASNS_NOT_IN_BGP": row.get("IRR_ORIGIN_ASNS_NOT_IN_BGP", ""),
            "BGP_ORIGIN_ASNS_WITHOUT_EXACT_IRR": row.get("BGP_ORIGIN_ASNS_WITHOUT_EXACT_IRR", ""),
            "RDAP_SAMPLE_CONSISTENCY": row.get("RDAP_SAMPLE_CONSISTENCY", ""),
            "RDAP_COUNTRIES": row.get("RDAP_COUNTRIES", ""),
            "TRIAGE_FLAGS": row.get("TRIAGE_FLAGS", ""),
            "REQUIRED_NEXT_ACTION": ACTIONS[name],
            "EVIDENCE_FRESHNESS_WARNING": "BGP origins come from the pinned 90-day archive; refresh exact NLRI and VRPs before any policy decision.",
            "EXTERNAL_SPOT_CHECK_STATUS": spot.get("STATUS", "NOT_SPOT_CHECKED"),
            "EXTERNAL_SPOT_CHECK_PREFIXES": spot.get("OBSERVED_PREFIXES", ""),
            "EXTERNAL_SPOT_CHECK_SCOPE_RELATION": spot_scope_relations.get(prefix, "NOT_SPOT_CHECKED"),
            "EXTERNAL_SPOT_CHECK_SUMMARY": spot.get("SUMMARY", ""),
            "EXTERNAL_SPOT_CHECK_SOURCE_URLS": spot.get("SOURCE_URLS", ""),
            "STATUS": "REVIEW",
        })
        priorities[priority] += 1
        tracks[name] += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        stream.write("# Review-only worklist; order is investigative urgency, not an approval or ownership verdict.\n")
        stream.write("# All rows stay REVIEW; no DIRECT policy or production dataset is changed.\n")
        writer = csv.DictWriter(stream, fieldnames=HEADER, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(result)
    stats = [
        "Artifact: v37 priority-prefix analyst worklist",
        f"Priority prefixes: {len(result)}", f"MOAS prefixes: {scope[1]}",
        f"Company-only prefixes: {scope[2]}", f"External spot-check rows: {len(spots)}",
        "All rows: STATUS=REVIEW; no row is approved, rejected, added to DIRECT or removed from DIRECT.",
        "Review order is evidence-refresh priority only, not a risk verdict or legal conclusion.",
        "The BGP input is a pinned 90-day archive; current BGP, IRR and RPKI must be refreshed before any policy decision.",
        "Related more-specific NLRI are never projected onto a covering prefix without exact-prefix evidence.",
    ]
    stats.extend(f"Track {k}: {v}" for k, v in sorted(tracks.items()))
    stats.extend(f"Priority {k}: {v}" for k, v in sorted(priorities.items()))
    stats.extend(
        f"External spot-check scope {relation}: {count}"
        for relation, count in sorted(Counter(spot_scope_relations.values()).items())
    )
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text("\n".join(stats) + "\n", encoding="utf-8")
    return {"rows": len(result), "priorities": dict(priorities), "tracks": dict(tracks), "spot_checks": len(spots)}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(build_worklist(args.evidence_dir, args.output, args.stats))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
