#!/usr/bin/env python3
"""Read-only regression detector for ALL published hard/DIRECT exception classes.

A stored observation is NOT an approval. Warn when the IPv4 host set changes,
even if the address counts remain identical, or when current ip.lst overlap
grows. This never modifies or fails a production GeoIP release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

CATEGORIES = ("CORE_CORPORATE", "SHARED_INFRA", "OTHER")

def compare(baseline, summary, files):
    if baseline.get("schema") != 1 or baseline.get("observation_only_not_approved") is not True:
        raise ValueError("Unverified or approval-ambiguous observation baseline")
    groups = summary.get("by_family", {}).get("ipv4", {}).get("by_origin_class", {})
    if set(groups) != set(CATEGORIES) or set(baseline.get("categories", {})) != set(CATEGORIES):
        raise ValueError("Required class-specific audit fields missing")
    changes = []
    for cat in CATEGORIES:
        expected, observed = baseline["categories"][cat], groups[cat]
        payload = files[cat]
        digest = hashlib.sha256(payload).hexdigest()
        if digest != expected["cidr_list_sha256"]:
            changes.append({"class":cat,"type":"CIDR_SET_CHANGED",
                            "baseline_sha256":expected["cidr_list_sha256"],"current_sha256":digest})
        for field, source in (("ipv4_addresses", "addresses"),
                              ("current_ip_lst_addresses", "current_antifilter_ip_addresses")):
            old, new = expected[field], observed[source]
            if new != old:
                changes.append({"class":cat,"type":field.upper()+"_CHANGED",
                                "baseline":old,"current":new,"delta":new-old})
    return {"baseline_is_approval":False,
            "number_of_observation_changes":len(changes),
            "observation_changes":changes,
            "action":"AUDIT_WARNING_ONLY",
            "requires_host_specific_review":bool(changes)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--cidr-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    baseline=json.loads(args.baseline.read_text(encoding="utf-8"))
    summary=json.loads(args.summary.read_text(encoding="utf-8"))
    files={cat:(args.cidr_dir/f"ipv4_hard_overrides_{cat.lower()}.txt").read_bytes()
           for cat in CATEGORIES}
    report=compare(baseline,summary,files)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"hard_override_class_regressions.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for row in report["observation_changes"]:
        print("::warning title=GeoIP v41 hard override observation changed::"+
              f"{row['class']}: {row['type']}; compare exact host lists; observation baseline is NOT approval")
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
