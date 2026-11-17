#!/usr/bin/env python3
"""Validate and report critical-service evidence without creating routing rules."""
import argparse
import csv
from datetime import date, datetime, timezone
from pathlib import Path
import re
from urllib.parse import urlsplit

HEADER = ["service_name", "domains", "asn_or_cidr", "evidence_type", "verified_date", "evidence_url", "source_scope", "routing_hint"]
HOST = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def read_inventory(path, *, as_of=None):
    today = as_of or datetime.now(timezone.utc).date()
    result, names, domains = [], set(), set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != HEADER:
            raise ValueError(f"{path}: invalid service inventory header")
        for row in reader:
            if None in row or any(not row.get(k) or row[k] != row[k].strip() for k in HEADER):
                raise ValueError(f"{path}:{reader.line_num}: missing or malformed field")
            name, domain = row["service_name"], row["domains"]
            if name in names or domain in domains or not HOST.fullmatch(domain):
                raise ValueError(f"{path}:{reader.line_num}: invalid or duplicate service/domain")
            names.add(name)
            domains.add(domain)
            url = urlsplit(row["evidence_url"])
            if (url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment
                    or any(c.isspace() for c in row["evidence_url"])):
                raise ValueError(f"{path}:{reader.line_num}: invalid evidence URL")
            verified = date.fromisoformat(row["verified_date"])
            if verified.isoformat() != row["verified_date"] or verified > today:
                raise ValueError(f"{path}:{reader.line_num}: evidence date is in the future")
            if (row["evidence_type"] != "OFFICIAL_DOMAIN" or row["source_scope"] != "LOCAL_CRITICAL"
                    or row["routing_hint"] != "DOMAIN_REVIEW" or row["asn_or_cidr"] != "-"):
                raise ValueError(f"{path}:{reader.line_num}: unsupported evidence claim or inferred routing")
            result.append(row)
    if not result:
        raise ValueError("service inventory is empty")
    return result


def format_report(rows):
    result = ["## Critical service inventory (review only)", "",
              "Official domain evidence only; no claim of Ministry whitelist membership, IP reachability or dedicated CIDRs.", "",
              "| Service | Domain | Mapping | Verified |", "|---|---|---|---|"]
    for row in rows:
        # Values are repository-reviewed metadata, but escaping keeps the Markdown table well formed.
        name = row["service_name"].replace("|", "\\|").replace("\n", " ")
        result.append(f"| {name} | `{row['domains']}` | domain review; no ASN/CIDR asserted | {row['verified_date']} |")
    return "\n".join(result) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        report = format_report(read_inventory(args.inventory))
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as stream:
            stream.write(report)
    print(report)


if __name__ == "__main__":
    main()
