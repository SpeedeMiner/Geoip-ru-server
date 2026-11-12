#!/usr/bin/env python3
"""Build a complete, review-only host-by-host evidence matrix for every v41
hard-source address still in DIRECT. No inference of current RKN blocking."""
from __future__ import annotations
import argparse
import csv
import ipaddress
import json
from collections import Counter
from pathlib import Path

from audit_v41_legacy_hard_evidence import tagged_networks
from audit_v41_service_hard_overrides import load_pinned_sources, most_specific_containing

CLASSES = ("CORE_CORPORATE", "SHARED_INFRA", "OTHER")

def read_ip_hosts(path):
    hosts = set()
    for row in path.read_text(encoding="utf-8").splitlines():
        token = row.split("#", 1)[0].strip()
        if not token:
            continue
        net = ipaddress.ip_network(token, strict=True)
        if net.version != 4:
            raise ValueError(f"Only IPv4 hard exception hosts expected: {net}")
        if net.num_addresses > 65536:
            raise ValueError("Unusually broad override mask; review before enumeration")
        hosts.update(net.hosts() if net.prefixlen < 31 else net)
    return hosts

def build_matrix(class_hosts, hard_rows, service_sources, core, shared):
    owner = {}
    for label, hosts in class_hosts.items():
        for ip in hosts:
            if ip in owner:
                raise ValueError(f"Host classified twice: {ip}")
            owner[ip] = label
    source_by_ip = {}
    for net, labels in hard_rows:
        if net.version != 4:
            continue
        for ip in owner:
            if ip in net:
                source_by_ip.setdefault(ip, set()).update(labels)
    if set(owner) != set(source_by_ip):
        raise ValueError("Some DIRECT hard exceptions lack original hard source evidence")
    report=[]
    for ip in sorted(owner):
        sources=source_by_ip[ip]
        src_services=[]
        exact_services=[]
        broad_services=[]
        for source, networks in sorted(service_sources.items()):
            matches=most_specific_containing(ip, networks)
            if matches:
                src_services.append(source)
                if any(p.prefixlen==32 for p in matches):
                    exact_services.append(source)
                if any(p.prefixlen<=24 for p in matches):
                    broad_services.append(source)
        matched_core=most_specific_containing(ip,core)
        matched_shared=most_specific_containing(ip,shared)
        label=owner[ip]
        if label=="CORE_CORPORATE" and not matched_core:
            raise ValueError(f"Missing CORE evidence: {ip}")
        if label=="SHARED_INFRA" and (matched_core or not matched_shared):
            raise ValueError(f"Ambiguous SHARED class: {ip}")
        if label=="OTHER" and (matched_core or matched_shared):
            raise ValueError(f"OTHER intersects protected origin ASN: {ip}")
        current_ip="antifilter-ip.lst" in sources
        current_subnet="antifilter-subnet.lst" in sources
        historical="v38-baseline-hard-or-unclassified" in sources
        # This is a review priority, NOT an instruction to change routing.
        rank=("P1_CURRENT_HARD_SHARED_OR_OTHER" if current_ip and label!="CORE_CORPORATE"
              else "P2_CURRENT_HARD_CORE" if current_ip
              else "P3_CURRENT_SUBNET" if current_subnet
              else "P4_LEGACY_OR_OTHER")
        report.append({
            "host":str(ip)+"/32","origin_class":label,
            "current_ip_lst":"YES" if current_ip else "NO",
            "current_subnet_lst":"YES" if current_subnet else "NO",
            "legacy_v38":"YES" if historical else "NO",
            "hard_source_labels":",".join(sorted(sources)),
            "core_prefix":str(matched_core[0]) if matched_core else "",
            "shared_prefix":str(matched_shared[0]) if matched_shared else "",
            "service_sources":",".join(src_services),
            "exact_32_service_sources":",".join(exact_services),
            "broad_24_or_wider_service_sources":",".join(broad_services),
            "service_evidence_present":"YES" if src_services else "NO",
            "review_priority":rank,
            "current_regulatory_block_confirmed":"NO",
            "service_host_ownership_confirmed":"NO",
            "policy_action":"NONE_AUDIT_ONLY",
        })
    return report

def summary(rows):
    priorities=Counter(r["review_priority"] for r in rows)
    byclass={}
    for group in CLASSES:
        selected=[r for r in rows if r["origin_class"]==group]
        byclass[group]={
            "hosts":len(selected),
            "current_ip_lst":sum(r["current_ip_lst"]=="YES" for r in selected),
            "current_subnet_lst":sum(r["current_subnet_lst"]=="YES" for r in selected),
            "legacy_v38":sum(r["legacy_v38"]=="YES" for r in selected),
            "exact_service_claim":sum(bool(r["exact_32_service_sources"]) for r in selected),
            "broad_service_claim":sum(bool(r["broad_24_or_wider_service_sources"]) for r in selected),
            "no_service_claim":sum(r["service_evidence_present"]=="NO" for r in selected),
        }
    return {"total_hosts":len(rows),"by_class":byclass,
            "current_ip_lst":sum(x["current_ip_lst"]=="YES" for x in rows),
            "priorities":dict(sorted(priorities.items())),
            "output_is_routing_change":False,
            "absence_of_current_block_proof_is_not_evidence_of_unblocking":True}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ("cidr_dir","hard","core_prefixes","shared_prefixes",
                  "kyoresuas_v4","kyoresuas_v6","kyoresuas_services",
                  "w1zardz","hxehex_ip","escapingworm","output_dir"):
        parser.add_argument("--"+field.replace("_","-"),type=Path,required=True)
    a=parser.parse_args()
    groups={
        cls:read_ip_hosts(a.cidr_dir/f"ipv4_hard_overrides_{cls.lower()}.txt")
        for cls in CLASSES
    }
    sources, core, shared=load_pinned_sources(a)
    rows=build_matrix(groups,tagged_networks(a.hard),sources,core,shared)
    if not rows:
        raise ValueError("Unexpected empty hard override matrix")
    output=summary(rows)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    with (a.output_dir/"all_153_hard_exceptions_evidence_matrix.tsv").open("w",encoding="utf-8",newline="") as fh:
        writer=csv.DictWriter(fh,fieldnames=list(rows[0]),delimiter="\t")
        writer.writeheader();writer.writerows(rows)
    (a.output_dir/"all_hard_evidence_matrix_summary.json").write_text(
        json.dumps(output,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
