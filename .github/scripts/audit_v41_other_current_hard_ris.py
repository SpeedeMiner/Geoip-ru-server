#!/usr/bin/env python3
"""Independent RIPE RIS origin observations for hard-overridden DIRECT outside CORE/SHARED.

Selection is address-precise, including non-/32 hard sources. BGP origins
are observations, NOT evidence of RKN block status or corporate affiliation.
"""
from __future__ import annotations
import argparse
import csv
import ipaddress
import json
from collections import Counter
from pathlib import Path
from audit_v41_current_hard_ris import annotate
from audit_v41_legacy_hard_evidence import tagged_networks

def expand_selected(path: Path, max_addresses=1000):
    addresses = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        net = ipaddress.ip_network(line, strict=True)
        if net.version != 4 or net.prefixlen == 0:
            raise ValueError(f"Invalid OTHER IPv4 CIDR at line {lineno}: {net}")
        if len(addresses) + net.num_addresses > max_addresses:
            raise ValueError("Too many OTHER hard-override addresses to query")
        addresses.extend(str(x) for x in net)
    if len(set(addresses)) != len(addresses) or not addresses:
        raise ValueError("Duplicate or missing OTHER addresses")
    return sorted(addresses, key=lambda x: int(ipaddress.ip_address(x)))

def build_rows(selected, hard_rows):
    current = []
    for ip in selected:
        address = ipaddress.ip_address(ip)
        labels = set().union(*(tags for net, tags in hard_rows if net.version == 4 and address in net))
        if not labels:
            raise ValueError(f"OTHER host is not in the original hard mask: {ip}")
        current.append({"prefix": ip + "/32", "evidence_sources": ",".join(sorted(labels)),
                        "origin_class": "OTHER", "policy_change": "NO"})
    return current

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--other-cidrs", type=Path, required=True)
    parser.add_argument("--hard", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    ips = expand_selected(args.other_cidrs)
    original = build_rows(ips, tagged_networks(args.hard))
    lookup, summary = annotate(original)
    count_current = sum("antifilter-ip.lst" in x["evidence_sources"].split(",") for x in original)
    if count_current != len(lookup):
        raise ValueError("Inconsistent current-source host selection")
    summary["other_total_hard_direct_addresses"] = len(original)
    summary["other_hard_without_current_ip_lst"] = len(original) - count_current
    summary["classification_change"] = "NONE"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "other_current_hard_ris_evidence.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(lookup[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(lookup)
    (args.output_dir / "other_current_hard_ris_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
