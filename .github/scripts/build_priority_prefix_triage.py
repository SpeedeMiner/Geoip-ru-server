#!/usr/bin/env python3
"""Build a deterministic, review-only triage table for the v37 priority prefixes.

The table joins existing RDAP, RPKI, IRR and BGP evidence. It makes no ownership,
DIRECT-suitability, approval or rejection decision. Every row remains REVIEW.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

EXPECTED_SCOPE: tuple[int, int, int] | None = None  # derive scope from the generated exact-prefix inventory
GOOD_IRR_QUERY_STATUSES = {
    "OK", "NO_OBJECTS_IN_QUERIED_SOURCES", "NO_EXACT_ROUTE_OBJECT_IN_QUERY_RESULTS",
}
FLAG_ORDER = (
    "RPKI_INVALID_ASN", "RPKI_UNKNOWN", "RPKI_QUERY_ERROR",
    "IRR_ORIGIN_SET_DIFFERS_FROM_BGP", "IRR_NO_EXACT_OBJECT", "IRR_QUERY_ERROR",
    "RDAP_MULTIPLE_SAMPLE_OBJECTS", "RDAP_COUNTRY_MIXED", "RDAP_QUERY_ERROR",
    "COMPANY_ONLY", "MOAS",
)
HEADER = (
    "PREFIX", "FAMILY", "PRIORITY_REASON", "INCLUSION_BASIS",
    "COMPANY_ASNS", "GLOBAL_BGP_ORIGIN_ASNS", "GLOBAL_BGP_MOAS",
    "RDAP_SAMPLE_COUNT", "RDAP_SUCCESS_COUNT", "RDAP_SAMPLE_CONSISTENCY",
    "RDAP_RESOURCE_HANDLES", "RDAP_REGISTRANT_ENTITIES", "RDAP_COUNTRIES",
    "RDAP_REGISTERED_CIDRS",
    "RPKI_ORIGIN_PAIR_COUNT", "RPKI_VALID_ORIGINS", "RPKI_INVALID_ORIGINS",
    "RPKI_UNKNOWN_ORIGINS", "RPKI_QUERY_ERROR_ORIGINS", "RPKI_STATUS_BY_ORIGIN",
    "IRR_QUERY_STATUS", "IRR_UNIQUE_ROUTE_OBJECTS", "IRR_EXACT_OBJECTS",
    "IRR_EXACT_ORIGINS", "IRR_MATCHED_BGP_ORIGINS",
    "IRR_ORIGIN_ASNS_NOT_IN_BGP", "BGP_ORIGIN_ASNS_WITHOUT_EXACT_IRR",
    "TRIAGE_FLAGS", "STATUS",
)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(
                (line for line in stream if not line.startswith("#")), delimiter="\t"
            ))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not rows:
        raise ValueError(f"empty TSV: {path}")
    return rows


def _index_unique(rows: Iterable[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "").strip()
        if not value or value in result:
            raise ValueError(f"empty or duplicate {label} key: {value!r}")
        result[value] = row
    return result


def _asns(value: str) -> set[str]:
    values = {item.strip() for item in value.split(",") if item.strip()}
    invalid = sorted(item for item in values if not re.fullmatch(r"AS[0-9]+", item))
    if invalid:
        raise ValueError(f"invalid ASN token(s): {invalid}")
    return values


def _irr_asns(value: str) -> set[str]:
    values = {item.strip() for item in value.split("|") if item.strip()}
    invalid = sorted(item for item in values if not re.fullmatch(r"AS[0-9]+", item))
    if invalid:
        raise ValueError(f"invalid IRR ASN token(s): {invalid}")
    return values


def _countries(value: str) -> set[str]:
    tokens = re.split(r"[,|;\s]+", value.strip()) if value.strip() else []
    return {token.upper() for token in tokens if re.fullmatch(r"[A-Za-z]{2}", token)}


def _sort_prefix(prefix: str) -> tuple[int, int, int]:
    network = ipaddress.ip_network(prefix, strict=True)
    return network.version, int(network.network_address), network.prefixlen


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_triage(
    evidence_dir: Path,
    output: Path,
    stats_path: Path,
    expected_scope: tuple[int, int, int] | None = EXPECTED_SCOPE,
) -> dict[str, object]:
    names = {
        "priority": "priority_prefixes.tsv",
        "holder": "prefix_holder_review_summary.tsv",
        "rpki": "rpki_by_origin.tsv",
        "irr": "irr_prefix_summary.tsv",
        "objects": "irr_route_objects_deduplicated.tsv",
    }
    paths = {key: evidence_dir / name for key, name in names.items()}
    data = {key: _read_tsv(path) for key, path in paths.items()}

    priority = _index_unique(data["priority"], "PREFIX", "priority prefix")
    holder = _index_unique(data["holder"], "PREFIX", "RDAP summary prefix")
    irr = _index_unique(data["irr"], "PREFIX", "IRR summary prefix")
    if set(priority) != set(holder) or set(priority) != set(irr):
        raise ValueError("priority, RDAP and IRR prefix inventories do not match exactly")

    if expected_scope is not None:
        moas_count = sum(row["GLOBAL_BGP_MOAS"].lower() == "yes" for row in priority.values())
        company_only_count = sum(row["INCLUSION_BASIS"] == "COMPANY_ASN_ONLY" for row in priority.values())
        observed = (len(priority), moas_count, company_only_count)
        if observed != expected_scope:
            raise ValueError(
                f"priority scope changed: expected {expected_scope}, observed {observed}; "
                "review the pinned scope before updating"
            )

    required_origin_pairs: set[tuple[str, str]] = set()
    origins_by_prefix: dict[str, set[str]] = {}
    for prefix, row in priority.items():
        network = ipaddress.ip_network(prefix, strict=True)
        if row.get("STATUS") != "REVIEW":
            raise ValueError(f"priority row is not REVIEW: {prefix}")
        if row.get("FAMILY") != f"IPv{network.version}":
            raise ValueError(f"priority family mismatch: {prefix}")
        origins = _asns(row.get("GLOBAL_BGP_ORIGIN_ASNS", ""))
        if not origins:
            raise ValueError(f"priority prefix has no global BGP origin ASN: {prefix}")
        origins_by_prefix[prefix] = origins
        required_origin_pairs.update((prefix, asn) for asn in origins)
        hrow, irow = holder[prefix], irr[prefix]
        if hrow.get("STATUS") != "REVIEW" or irow.get("STATUS") != "REVIEW":
            raise ValueError(f"supporting evidence row is not REVIEW: {prefix}")
        if _asns(hrow.get("GLOBAL_BGP_ORIGIN_ASNS", "")) != origins:
            raise ValueError(f"RDAP summary BGP origin set differs from priority queue: {prefix}")

    rpki_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    for row in data["rpki"]:
        prefix, asn = row.get("PREFIX", ""), row.get("ORIGIN_ASN", "")
        key = (prefix, asn)
        if key in rpki_by_pair:
            raise ValueError(f"duplicate RPKI prefix/origin row: {key}")
        if key not in required_origin_pairs:
            raise ValueError(f"RPKI row is not a current priority BGP origin pair: {key}")
        if row.get("QUERY_STATUS") == "OK" and not row.get("RPKI_STATUS"):
            raise ValueError(f"RPKI status is empty after a successful query: {key}")
        rpki_by_pair[key] = row
    if set(rpki_by_pair) != required_origin_pairs:
        missing = sorted(required_origin_pairs - set(rpki_by_pair))[:10]
        extra = sorted(set(rpki_by_pair) - required_origin_pairs)[:10]
        raise ValueError(f"RPKI prefix/origin coverage mismatch; missing={missing}, extra={extra}")

    objects_by_prefix: dict[str, list[dict[str, str]]] = defaultdict(list)
    logical_keys: set[tuple[str, str, str, str]] = set()
    for row in data["objects"]:
        prefix = row.get("QUERY_PREFIX", "")
        key = (
            prefix, row.get("OBJECT_TYPE", ""), row.get("ROUTE_PREFIX", ""),
            row.get("ORIGIN_ASN", ""),
        )
        if key in logical_keys:
            raise ValueError(f"duplicate deduplicated logical IRR route object: {key}")
        logical_keys.add(key)
        if prefix not in priority:
            raise ValueError(f"IRR object query prefix is outside priority inventory: {prefix}")
        if row.get("EXACT_PREFIX_MATCH") == "yes" and row.get("ROUTE_PREFIX") != prefix:
            raise ValueError(f"IRR exact-match marker disagrees with route prefix: {key}")
        objects_by_prefix[prefix].append(row)

    output_rows: list[dict[str, str]] = []
    flag_counts: Counter[str] = Counter()
    for prefix in sorted(priority, key=_sort_prefix):
        prow, hrow, irow = priority[prefix], holder[prefix], irr[prefix]
        origins = origins_by_prefix[prefix]
        rpki_rows = {asn: rpki_by_pair[(prefix, asn)] for asn in sorted(origins)}
        valid = sorted(
            asn for asn, row in rpki_rows.items()
            if row.get("QUERY_STATUS") == "OK" and row.get("RPKI_STATUS") == "valid"
        )
        invalid = sorted(
            asn for asn, row in rpki_rows.items()
            if row.get("QUERY_STATUS") == "OK" and row.get("RPKI_STATUS") == "invalid_asn"
        )
        unknown = sorted(
            asn for asn, row in rpki_rows.items()
            if row.get("QUERY_STATUS") == "OK" and row.get("RPKI_STATUS") == "unknown"
        )
        rpki_errors = sorted(
            asn for asn, row in rpki_rows.items() if row.get("QUERY_STATUS") != "OK"
        )
        rpki_status = " | ".join(
            f"{asn}={rpki_rows[asn].get('RPKI_STATUS') or rpki_rows[asn].get('QUERY_STATUS')}"
            for asn in sorted(origins)
        )

        exact_objects = [
            row for row in objects_by_prefix[prefix] if row.get("EXACT_PREFIX_MATCH") == "yes"
        ]
        exact_origins = {row.get("ORIGIN_ASN", "") for row in exact_objects}
        if "" in exact_origins:
            raise ValueError(f"exact IRR object has empty origin ASN: {prefix}")
        exact_matches = {
            row.get("ORIGIN_ASN", "") for row in exact_objects
            if row.get("GLOBAL_BGP_ORIGIN_MATCH") == "yes"
        }
        if any(row.get("GLOBAL_BGP_ORIGIN_MATCH") not in {"yes", "no"} for row in exact_objects):
            raise ValueError(f"exact IRR object has invalid BGP-origin-match flag: {prefix}")
        summary_count = int(irow.get("IRR_EXACT_OBJECTS", "-1"))
        summary_unique = int(irow.get("IRR_UNIQUE_ROUTE_OBJECTS", "-1"))
        summary_matches = int(irow.get("IRR_EXACT_BGP_ORIGIN_MATCH_OBJECTS", "-1"))
        if summary_count != len(exact_objects):
            raise ValueError(
                f"IRR exact-object count mismatch for {prefix}: "
                f"summary={summary_count}, objects={len(exact_objects)}"
            )
        if summary_unique != len(objects_by_prefix[prefix]):
            raise ValueError(f"IRR unique-object count mismatch for {prefix}")
        if summary_matches != len(exact_matches):
            raise ValueError(f"IRR exact BGP-origin match count mismatch for {prefix}")
        if _irr_asns(irow.get("IRR_EXACT_ORIGINS", "")) != exact_origins:
            raise ValueError(f"IRR exact-origin set mismatch for {prefix}")
        if _irr_asns(irow.get("IRR_MATCHED_BGP_ORIGINS", "")) != exact_matches:
            raise ValueError(f"IRR matched-origin set mismatch for {prefix}")

        flags: list[str] = []
        if invalid:
            flags.append("RPKI_INVALID_ASN")
        if unknown:
            flags.append("RPKI_UNKNOWN")
        if rpki_errors:
            flags.append("RPKI_QUERY_ERROR")
        irr_query_status = irow.get("QUERY_STATUS", "")
        if irr_query_status not in GOOD_IRR_QUERY_STATUSES:
            flags.append("IRR_QUERY_ERROR")
        if summary_count == 0 and irr_query_status in GOOD_IRR_QUERY_STATUSES:
            flags.append("IRR_NO_EXACT_OBJECT")
        if summary_count > 0 and exact_origins != origins:
            flags.append("IRR_ORIGIN_SET_DIFFERS_FROM_BGP")
        if hrow.get("RDAP_SAMPLE_CONSISTENCY") == "MULTIPLE_RESOURCE_OBJECTS_AT_SAMPLES":
            flags.append("RDAP_MULTIPLE_SAMPLE_OBJECTS")
        if len(_countries(hrow.get("RDAP_COUNTRIES", ""))) > 1:
            flags.append("RDAP_COUNTRY_MIXED")
        try:
            rdap_count = int(hrow.get("RDAP_SAMPLE_COUNT", "0"))
            rdap_success = int(hrow.get("RDAP_SUCCESS_COUNT", "0"))
        except ValueError as exc:
            raise ValueError(f"invalid RDAP sample counters for {prefix}") from exc
        if rdap_success != rdap_count or bool(hrow.get("RDAP_QUERY_ERRORS", "").strip()):
            flags.append("RDAP_QUERY_ERROR")
        if prow.get("INCLUSION_BASIS") == "COMPANY_ASN_ONLY":
            flags.append("COMPANY_ONLY")
        if prow.get("GLOBAL_BGP_MOAS", "").lower() == "yes":
            flags.append("MOAS")

        flags = [flag for flag in FLAG_ORDER if flag in flags]
        flag_counts.update(flags)
        output_rows.append({
            "PREFIX": prefix,
            "FAMILY": prow["FAMILY"],
            "PRIORITY_REASON": prow["PRIORITY_REASON"],
            "INCLUSION_BASIS": prow["INCLUSION_BASIS"],
            "COMPANY_ASNS": prow["COMPANY_ASNS"],
            "GLOBAL_BGP_ORIGIN_ASNS": ",".join(sorted(origins)),
            "GLOBAL_BGP_MOAS": prow["GLOBAL_BGP_MOAS"],
            "RDAP_SAMPLE_COUNT": str(rdap_count),
            "RDAP_SUCCESS_COUNT": str(rdap_success),
            "RDAP_SAMPLE_CONSISTENCY": hrow["RDAP_SAMPLE_CONSISTENCY"],
            "RDAP_RESOURCE_HANDLES": hrow.get("RDAP_RESOURCE_HANDLES", ""),
            "RDAP_REGISTRANT_ENTITIES": hrow.get("RDAP_REGISTRANT_ENTITIES", ""),
            "RDAP_COUNTRIES": hrow.get("RDAP_COUNTRIES", ""),
            "RDAP_REGISTERED_CIDRS": hrow.get("RDAP_REGISTERED_CIDRS", ""),
            "RPKI_ORIGIN_PAIR_COUNT": str(len(rpki_rows)),
            "RPKI_VALID_ORIGINS": ",".join(valid),
            "RPKI_INVALID_ORIGINS": ",".join(invalid),
            "RPKI_UNKNOWN_ORIGINS": ",".join(unknown),
            "RPKI_QUERY_ERROR_ORIGINS": ",".join(rpki_errors),
            "RPKI_STATUS_BY_ORIGIN": rpki_status,
            "IRR_QUERY_STATUS": irr_query_status,
            "IRR_UNIQUE_ROUTE_OBJECTS": str(summary_unique),
            "IRR_EXACT_OBJECTS": str(summary_count),
            "IRR_EXACT_ORIGINS": " | ".join(sorted(exact_origins)),
            "IRR_MATCHED_BGP_ORIGINS": " | ".join(sorted(exact_matches)),
            "IRR_ORIGIN_ASNS_NOT_IN_BGP": " | ".join(sorted(exact_origins - origins)),
            "BGP_ORIGIN_ASNS_WITHOUT_EXACT_IRR": " | ".join(sorted(origins - exact_origins)),
            "TRIAGE_FLAGS": " | ".join(flags),
            "STATUS": "REVIEW",
        })

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        stream.write("# Review-only triage; no ownership or DIRECT decision is inferred.\n")
        stream.write("# Flags are deterministic joins of the v37 priority, RDAP, RPKI and deduplicated IRR evidence tables.\n")
        writer = csv.DictWriter(stream, fieldnames=HEADER, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    input_hashes = {names[key]: _digest(path) for key, path in paths.items()}
    stats_lines = [
        "Artifact: v37 priority-prefix triage",
        f"Priority prefixes: {len(output_rows)}",
        f"Exact-MOAS prefixes: {sum(row['GLOBAL_BGP_MOAS'].lower() == 'yes' for row in output_rows)}",
        f"Company-only prefixes: {sum(row['INCLUSION_BASIS'] == 'COMPANY_ASN_ONLY' for row in output_rows)}",
        f"RPKI prefix/origin pairs: {sum(int(row['RPKI_ORIGIN_PAIR_COUNT']) for row in output_rows)}",
        f"Prefixes with RPKI_INVALID_ASN: {flag_counts['RPKI_INVALID_ASN']}",
        f"Prefixes with RPKI_UNKNOWN: {flag_counts['RPKI_UNKNOWN']}",
        f"Prefixes with IRR_ORIGIN_SET_DIFFERS_FROM_BGP: {flag_counts['IRR_ORIGIN_SET_DIFFERS_FROM_BGP']}",
        f"Prefixes with IRR_NO_EXACT_OBJECT: {flag_counts['IRR_NO_EXACT_OBJECT']}",
        f"Prefixes with RDAP_MULTIPLE_SAMPLE_OBJECTS: {flag_counts['RDAP_MULTIPLE_SAMPLE_OBJECTS']}",
        f"Prefixes with RDAP_COUNTRY_MIXED: {flag_counts['RDAP_COUNTRY_MIXED']}",
        "All rows: STATUS=REVIEW; no row is automatically approved, rejected, added to DIRECT or removed from DIRECT.",
        "RPKI flags apply only to exact prefix/origin pairs for global BGP origins in the same archived snapshot.",
        "IRR origin-set difference compares deduplicated exact route-object origins with the complete observed BGP origin-ASN set; both set differences are retained in the TSV.",
        "IRR absence means no exact object in the eight RIPE Database/GRS sources queried by the upstream evidence collector, not global IRR absence.",
        "RDAP multiple-object and mixed-country flags are based on first/middle/last address samples; they are review signals, not exhaustive prefix ownership proof.",
    ]
    stats_lines.extend(
        f"Input SHA256 {name}: {digest}" for name, digest in sorted(input_hashes.items())
    )
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text("\n".join(stats_lines) + "\n", encoding="utf-8")
    return {
        "rows": len(output_rows),
        "rpki_pairs": sum(int(row["RPKI_ORIGIN_PAIR_COUNT"]) for row in output_rows),
        "flag_counts": dict(flag_counts),
        "input_hashes": input_hashes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_triage(args.evidence_dir, args.output, args.stats)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
