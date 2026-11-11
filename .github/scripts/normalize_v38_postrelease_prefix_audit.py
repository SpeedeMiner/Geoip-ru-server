#!/usr/bin/env python3
"""Normalize only presentation aliases in RouteViews RPKI labels.

Raw source values remain in the TSV and JSONL. This tool creates separate
semantic-conflict and spelling-variant fields; it never changes STATUS.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def canonical_status(value: Any) -> str:
    """Canonicalize known textual aliases without treating missing as valid."""
    raw = str(value).strip().casefold()
    compact = "".join(ch for ch in raw if ch.isalnum())
    if compact == "notfound":
        return "not-found"
    return raw


def compare_rpki_views(
    route_level: dict[str, str], vrp_snapshot: dict[str, str]
) -> tuple[str, dict[str, dict[str, str]], list[str], list[str], dict[str, dict[str, str]]]:
    """Return view class, real status conflicts, origin-only lists, and label aliases."""
    common = set(route_level) & set(vrp_snapshot)
    conflicts = {
        asn: {
            "near_realtime_route_level": route_level[asn],
            "two_hour_aggregate_snapshot": vrp_snapshot[asn],
        }
        for asn in sorted(common)
        if canonical_status(route_level[asn]) != canonical_status(vrp_snapshot[asn])
    }
    label_variants = {
        asn: {
            "near_realtime_route_level": route_level[asn],
            "two_hour_aggregate_snapshot": vrp_snapshot[asn],
        }
        for asn in sorted(common)
        if route_level[asn] != vrp_snapshot[asn]
        and canonical_status(route_level[asn]) == canonical_status(vrp_snapshot[asn])
    }
    route_only = sorted(set(route_level) - set(vrp_snapshot))
    vrp_only = sorted(set(vrp_snapshot) - set(route_level))

    if not route_level:
        classification = "NO_EXACT_ROUTE"
    elif not vrp_snapshot:
        classification = "NO_TIMESTAMPED_VRP_STATE"
    elif conflicts:
        classification = "SAME_ORIGIN_STATUS_DIFFERS"
    elif route_only or vrp_only:
        classification = "ORIGIN_SET_DIFFERS"
    else:
        classification = "ORIGIN_SETS_AND_STATES_MATCH"
    return classification, conflicts, route_only, vrp_only, label_variants


def process_audit_dir(root: Path) -> dict[str, Any]:
    tsv = root / "v38_postrelease_prefix_review.tsv"
    manifest_path = root / "manifest.json"
    with tsv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    required = {"PREFIX", "STATUS", "ROUTEVIEWS_ROUTE_LEVEL_RPKI", "ROUTEVIEWS_VRP_ORIGIN_STATES"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"Missing required TSV columns: {missing}")
    additions = [
        "RPKI_VIEW_COMPARISON",
        "ROUTE_LEVEL_RPKI_ONLY_ORIGINS",
        "TIMESTAMPED_VRP_ONLY_ORIGINS",
        "RPKI_STATUS_CONFLICTS",
        "RPKI_STATUS_LABEL_VARIANTS",
    ]
    for name in additions:
        if name not in fields:
            fields.append(name)

    view_counts: Counter[str] = Counter()
    conflicts_all: list[dict[str, Any]] = []
    variants_all: list[dict[str, Any]] = []
    for row in rows:
        route = json.loads(row["ROUTEVIEWS_ROUTE_LEVEL_RPKI"] or "{}")
        snapshot = json.loads(row["ROUTEVIEWS_VRP_ORIGIN_STATES"] or "{}")
        classification, conflicts, route_only, vrp_only, variants = compare_rpki_views(route, snapshot)
        row["RPKI_VIEW_COMPARISON"] = classification
        row["ROUTE_LEVEL_RPKI_ONLY_ORIGINS"] = json.dumps(route_only, separators=(",", ":"))
        row["TIMESTAMPED_VRP_ONLY_ORIGINS"] = json.dumps(vrp_only, separators=(",", ":"))
        row["RPKI_STATUS_CONFLICTS"] = json.dumps(conflicts, sort_keys=True, separators=(",", ":"))
        row["RPKI_STATUS_LABEL_VARIANTS"] = json.dumps(variants, sort_keys=True, separators=(",", ":"))
        view_counts[classification] += 1
        if conflicts:
            conflicts_all.append({"prefix": row["PREFIX"], "conflicts": conflicts})
        if variants:
            variants_all.append({"prefix": row["PREFIX"], "label_variants": variants})

    if len(rows) != 56:
        raise ValueError(f"Expected 56 rows, got {len(rows)}")
    if any(row["STATUS"] != "REVIEW" for row in rows):
        raise ValueError("All rows must remain REVIEW")

    with tsv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["route_level_vs_vrp_snapshot_counts"] = dict(sorted(view_counts.items()))
    manifest["route_level_vs_vrp_status_conflicts"] = conflicts_all
    manifest["route_level_vs_vrp_status_label_variants"] = variants_all
    manifest["rpki_status_normalization"] = {
        "canonical_rule": "casefold and remove non-alphanumeric separators for comparison; known compact token 'notfound' is represented as 'not-found'",
        "raw_source_values_preserved": True,
        "meaning": "Formatting-only aliases are recorded separately and are not classified as semantic status conflicts.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = {
        "rows": len(rows),
        "status_counts": dict(sorted(view_counts.items())),
        "semantic_conflicts": conflicts_all,
        "label_variants": variants_all,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    args = parser.parse_args()
    process_audit_dir(args.input_dir)


if __name__ == "__main__":
    main()
