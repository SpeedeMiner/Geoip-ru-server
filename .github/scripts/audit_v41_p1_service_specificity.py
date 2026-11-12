#!/usr/bin/env python3
"""Subdivide current hard + service-protected DIRECT risks without routing changes.

A catalogue's /32 claim is not proof the host belongs to the named service.
No source combination alone establishes an active regulator block.
"""
from __future__ import annotations
import argparse
import csv
import ipaddress
import json
from collections import Counter
from pathlib import Path

def classify(row):
    if row["review_priority"] != "P1_CURRENT_HARD_SHARED_OR_OTHER":
        return None
    if row["origin_class"] not in {"SHARED_INFRA", "OTHER"} or row["current_ip_lst"] != "YES":
        raise ValueError(f"Inconsistent P1 record: {row['host']}")
    exact=bool(row["exact_32_service_sources"].strip())
    broad=bool(row["broad_24_or_wider_service_sources"].strip())
    if broad and exact:
        label="P1_BROAD_AND_EXACT"
    elif broad:
        label="P1_BROAD_ONLY"
    elif exact:
        label="P1_EXACT_ONLY"
    elif row["service_evidence_present"]=="YES":
        label="P1_NARROW_OR_UNSPECIFIED"
    else:
        label="P1_NO_SERVICE_CLAIM"
    return label

def triage(rows):
    seen=set()
    reviewed=[]
    for row in rows:
        net=ipaddress.ip_network(row["host"],strict=True)
        if net.version!=4 or net.prefixlen!=32 or str(net) in seen:
            raise ValueError(f"Invalid/duplicate exact host: {net}")
        seen.add(str(net))
        tier=classify(row)
        if tier is None:
            continue
        origin=row["origin_class"]
        # Ordering controls review workload only. Never changes production masks.
        reviewed.append({**row,
           "service_specificity_tier":tier,
           "manual_review_order": "1" if tier=="P1_BROAD_ONLY" else
                                  "2" if tier=="P1_BROAD_AND_EXACT" else
                                  "3" if tier=="P1_EXACT_ONLY" else "4",
           "regulator_ip_specific_evidence":"NOT_VERIFIED",
           "first_party_service_host_evidence":"NOT_VERIFIED",
           "needs_independent_dated_ip_and_service_proof":"YES",
           "routing_change_authorized":"NO"})
    reviewed.sort(key=lambda r:(int(r["manual_review_order"]),int(ipaddress.ip_network(r["host"]).network_address)))
    counts=Counter(r["service_specificity_tier"] for r in reviewed)
    byclass={name:dict(sorted(Counter(
        r["service_specificity_tier"] for r in reviewed if r["origin_class"]==name
    ).items())) for name in ("SHARED_INFRA","OTHER")}
    result={
        "total_p1_current_ip_lst":len(reviewed),
        "service_specificity_counts":dict(sorted(counts.items())),
        "origin_class_specificity":byclass,
        "total_matches_precedence_p1":True,
        "active_regulatory_blocks_established":0,
        "routing_changes_applied":0,
        "known_limitation":"Feed membership and catalog claim are not current regulator or service ownership evidence"
    }
    return reviewed,result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args()
    with a.matrix.open(encoding="utf-8",newline="") as fh:
        rows=list(csv.DictReader(fh,delimiter="\t"))
    if not rows:
        raise ValueError("Nonempty complete hard exception matrix required")
    out,stats=triage(rows)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    with (a.output_dir/"p1_current_hard_service_specificity_review.tsv").open("w",encoding="utf-8",newline="") as fh:
        writer=csv.DictWriter(fh,fieldnames=list(out[0]),delimiter="\t")
        writer.writeheader();writer.writerows(out)
    (a.output_dir/"p1_current_hard_review_summary.json").write_text(
        json.dumps(stats,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(stats,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
