#!/usr/bin/env python3
"""Attribute current v41 SHARED hard-block overrides to *named* service entries.

Service-catalog membership is a routing claim by its publisher. It is not proof
of IP ownership, a current RKN block, or independent first-party authorization.
"""
from __future__ import annotations

import argparse
import csv
import ipaddress
import json
from collections import Counter
from pathlib import Path


def named_services(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc.get("categories"), list):
        raise ValueError("Missing Kyoresuas categories")
    records = []
    for category in doc["categories"]:
        if not isinstance(category, dict):
            continue
        for service in category.get("services", []) or []:
            if not isinstance(service, dict) or str(service.get("tier", "")).lower() not in {"lite", "standard"}:
                continue
            for token in service.get("ipv4", []) or []:
                net = ipaddress.ip_network(token, strict=True)
                if net.version != 4 or net.prefixlen == 0:
                    raise ValueError("Invalid or default-route Kyoresuas IPv4 service prefix")
                records.append({
                    "prefix": net,
                    "service": str(service.get("name", "")).replace("\t", " ").replace("\n", " "),
                    "category": str(category.get("id", "")),
                    "tier": str(service.get("tier", "")).lower(),
                    "asn_claims": ",".join(str(x) for x in service.get("asns", []) or []),
                })
    if not records:
        raise ValueError("Kyoresuas has no named IPv4 service entries")
    return records


def explain(host, records):
    matches = [x for x in records if host in x["prefix"]]
    matches.sort(key=lambda x: (-x["prefix"].prefixlen, x["service"], str(x["prefix"])))
    names = sorted({x["service"] for x in matches if x["service"]})
    exact_hosts = [x for x in matches if x["prefix"].prefixlen == 32]
    broad = [x for x in matches if x["prefix"].prefixlen <= 24]
    return {
        "named_services": "; ".join(names),
        "named_service_count": len(names),
        "most_specific_named_prefix": str(matches[0]["prefix"]) if matches else "",
        "named_prefixes": "; ".join(sorted({str(x["prefix"]) for x in matches})),
        "named_categories": "; ".join(sorted({x["category"] for x in matches})),
        "named_tiers": "; ".join(sorted({x["tier"] for x in matches})),
        "exact_named_host": bool(exact_hosts),
        "broad_named_service": bool(broad),
        # Do not interpret the ASN field as observed IP origin; it is only an
        # upstream catalog-level claim for a service.
        "publisher_catalog_asns": "; ".join(sorted({x["asn_claims"] for x in matches if x["asn_claims"]})),
    }


def analyze(rows, records):
    result = []
    for row in rows:
        prefix = ipaddress.ip_network(row["prefix"], strict=True)
        if prefix.version != 4 or prefix.prefixlen != 32:
            raise ValueError(f"Expected IPv4 /32 in broad hard override audit: {prefix}")
        details = explain(prefix.network_address, records)
        is_current = "antifilter-ip.lst" in row["evidence_sources"].split(",")
        is_catalog = "kyoresuas-standard" in row["service_matches"].split(",")
        if is_catalog and not details["named_service_count"]:
            policy = "KYORE_SUAS_AGGREGATE_ONLY"
        elif not is_catalog:
            policy = "OTHER_SERVICE_SOURCE"
        elif details["exact_named_host"]:
            policy = "NAMED_EXACT_HOST"
        elif details["broad_named_service"]:
            policy = "NAMED_BROAD_SHARED"
        else:
            policy = "NAMED_NARROW_PREFIX"
        result.append({
            **row, **details,
            "current_antifilter_ip": "YES" if is_current else "NO",
            "evidence_priority": "HIGH_CURRENT_SHARED_HARD" if is_current else "HISTORICAL_REVIEW",
            "catalog_evidence_type": policy,
            "ip_specific_ownership_verified": "NO",
            "active_regulatory_block_verified": "NO",
            "automatic_routing_change": "NO",
        })
    if not result:
        raise ValueError("Empty hard override audit")
    buckets = Counter(row["catalog_evidence_type"] for row in result)
    return result, {
        "total_rows": len(result),
        "current_hard_rows": sum(row["current_antifilter_ip"] == "YES" for row in result),
        "historical_hard_rows": sum(row["current_antifilter_ip"] == "NO" for row in result),
        "named_catalog_rows": sum(row["named_service_count"] > 0 for row in result),
        "named_exact_host_rows": sum(row["exact_named_host"] for row in result),
        "named_broad_service_rows": sum(row["broad_named_service"] for row in result),
        "catalog_evidence_types": dict(sorted(buckets.items())),
        "manual_verification_required": True,
        "release_impact": "NONE_READ_ONLY",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overrides", type=Path, required=True)
    ap.add_argument("--services", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    with args.overrides.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    catalog = named_services(args.services)
    annotated, summary = analyze(rows, catalog)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dest = args.output_dir / "hard_service_named_attribution.tsv"
    with dest.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(annotated[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(annotated)
    (args.output_dir / "hard_service_named_attribution_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
