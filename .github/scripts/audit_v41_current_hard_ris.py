#!/usr/bin/env python3
"""Read-only RIPE RIS observed BGP origins for current Antifilter hard exceptions.

Routing evidence does not establish legal ownership, an active RKN block, or
whether a service actually occupies the IP address.
"""
from __future__ import annotations
import argparse
import csv
import ipaddress
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

URL = "https://stat.ripe.net/data/network-info/data.json"

def fetch_ris(ip):
    endpoint = URL + "?" + urllib.parse.urlencode({"resource": ip})
    req = urllib.request.Request(endpoint, headers={"User-Agent": "GeoIP-v41-review/1.0"})
    with urllib.request.urlopen(req, timeout=18) as response:
        return json.load(response)

def normalize_ris(ip, response):
    if not isinstance(response, dict) or response.get("status") != "ok":
        return {"ris_status": "UNKNOWN", "ris_prefix": "", "ris_asns": "", "ris_error": "invalid response"}
    data = response.get("data")
    if not isinstance(data, dict):
        return {"ris_status": "UNKNOWN", "ris_prefix": "", "ris_asns": "", "ris_error": "missing data"}
    prefix, asns = data.get("prefix"), data.get("asns")
    if not prefix or not isinstance(asns, list) or not asns:
        return {"ris_status": "NOT_OBSERVED", "ris_prefix": "", "ris_asns": "", "ris_error": ""}
    try:
        net = ipaddress.ip_network(prefix, strict=True)
        if ipaddress.ip_address(ip) not in net:
            raise ValueError("RIPE returned prefix not covering the queried IP")
        origins = sorted(set(int(x) for x in asns))
        if not origins or any(a <= 0 or a > 4294967295 for a in origins):
            raise ValueError("Invalid ASNs")
    except (ValueError, TypeError) as exc:
        return {"ris_status": "UNKNOWN", "ris_prefix": "", "ris_asns": "", "ris_error": str(exc)}
    return {"ris_status": "OBSERVED", "ris_prefix": str(net),
            "ris_asns": ",".join("AS" + str(x) for x in origins), "ris_error": ""}

def annotate(rows, lookup=fetch_ris, sleep_seconds=0.15):
    seen, out = set(), []
    for row in rows:
        net = ipaddress.ip_network(row["prefix"], strict=True)
        if net.version != 4 or net.prefixlen != 32 or str(net) in seen:
            raise ValueError(f"Invalid or duplicate host: {net}")
        seen.add(str(net))
        if "antifilter-ip.lst" not in row["evidence_sources"].split(","):
            continue
        ip = str(net.network_address)
        try:
            bgp = normalize_ris(ip, lookup(ip))
        except (OSError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as exc:
            bgp = {"ris_status": "UNKNOWN", "ris_prefix": "", "ris_asns": "",
                   "ris_error": str(exc)[:200]}
        out.append({**row, **bgp, "actual_rkn_block_verified": "NO",
                    "first_party_service_ip_verified": "NO",
                    "action": "AUDIT_ONLY"})
        if sleep_seconds:
            time.sleep(sleep_seconds)
    states = Counter(r["ris_status"] for r in out)
    asns = Counter(a for r in out if r["ris_status"] == "OBSERVED"
                   for a in r["ris_asns"].split(",") if a)
    return out, {
        "input_unique_hosts": len(seen),
        "current_antifilter_hard_hosts": len(out),
        "ris_observed": states["OBSERVED"],
        "ris_not_observed": states["NOT_OBSERVED"],
        "ris_unknown": states["UNKNOWN"],
        "observed_origin_asn_counts_nonexclusive": dict(sorted(asns.items())),
        "queried_at_utc": datetime.now(timezone.utc).isoformat(),
        "ris_api": URL,
        "limitation": "RIS routing evidence does not prove an active regulatory block or first-party IP ownership",
        "policy_change": "NONE",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    with args.attribution.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    if not rows or not {"prefix", "evidence_sources", "shared_prefix", "named_services"}.issubset(rows[0]):
        parser.error("Missing required attribution fields")
    results, summary = annotate(rows)
    if not results:
        parser.error("No current Antifilter hard hosts")
    args.output_dir.mkdir(exist_ok=True, parents=True)
    with (args.output_dir / "hard_current_ris_bgp_evidence.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(results[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(results)
    (args.output_dir / "hard_current_ris_bgp_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
