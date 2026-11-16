#!/usr/bin/env python3
"""Check reviewed address fixtures against DAT and decompiled sing-box rule-sets."""
import argparse
import csv
from datetime import date, datetime, timezone
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit

from build_v41_overlay import intervals, parse_geoip_dat

HEADER = ["service", "address", "expected", "evidence_type", "evidence_url", "verified_date", "review_after"]


def read_fixtures(path, *, as_of=None):
    today = as_of or datetime.now(timezone.utc).date()
    rows, seen = [], set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != HEADER:
            raise ValueError("invalid routing fixture schema")
        for row in reader:
            if None in row or any(not row.get(k) or row[k] != row[k].strip() for k in HEADER):
                raise ValueError(f"{path}:{reader.line_num}: missing or malformed field")
            address = ipaddress.ip_address(row["address"])
            if str(address) != row["address"] or str(address) in seen:
                raise ValueError(f"{path}:{reader.line_num}: noncanonical or duplicate address")
            seen.add(str(address))
            allowed = {"DIRECT": "OFFICIAL_SERVICE_IP", "PROXY": "VERIFIED_IP_UNREACHABLE"}
            if allowed.get(row["expected"]) != row["evidence_type"]:
                raise ValueError(f"{path}:{reader.line_num}: unsupported expectation/evidence")
            url = urlsplit(row["evidence_url"])
            if (url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment
                    or any(c.isspace() for c in row["evidence_url"])):
                raise ValueError(f"{path}:{reader.line_num}: invalid evidence URL")
            verified, review = date.fromisoformat(row["verified_date"]), date.fromisoformat(row["review_after"])
            if (verified.isoformat() != row["verified_date"] or review.isoformat() != row["review_after"]
                    or verified > today or review < verified or review < today):
                raise ValueError(f"{path}:{reader.line_num}: evidence date requires review")
            rows.append(row)
    if not rows:
        raise ValueError("routing fixture matrix is empty")
    return rows


def read_srs_source(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    rules = document.get("rules")
    if document.get("version") != 1 or not isinstance(rules, list) or len(rules) != 1 or set(rules[0]) != {"ip_cidr"}:
        raise ValueError(f"unexpected decompiled rule-set structure: {path}")
    if not isinstance(rules[0]["ip_cidr"], list) or not rules[0]["ip_cidr"]:
        raise ValueError(f"empty or invalid decompiled rule-set: {path}")
    return {ipaddress.ip_network(item, strict=True) for item in rules[0]["ip_cidr"]}


def validate_matrix(dat, sources, rows):
    categories = parse_geoip_dat(dat)
    if set(categories) != {"RU", "PRIVATE"} or set(sources) != {"RU", "PRIVATE"}:
        raise ValueError("expected RU and PRIVATE categories")
    for name in ("RU", "PRIVATE"):
        for family in (4, 6):
            if intervals(categories[name], family) != intervals(sources[name], family):
                raise ValueError(f"{name} IPv{family}: SRS coverage differs from DAT")
    for row in rows:
        address = ipaddress.ip_address(row["address"])
        direct = any(address.version == net.version and address in net for net in categories["RU"])
        private = any(address.version == net.version and address in net for net in categories["PRIVATE"])
        if private or direct != (row["expected"] == "DIRECT"):
            raise ValueError(f"routing fixture failed: {row['service']} ({address}) expected {row['expected']}")
    return {"fixtures": len(rows), "direct": sum(row["expected"] == "DIRECT" for row in rows),
            "proxy": sum(row["expected"] == "PROXY" for row in rows),
            "ipv4": sum(ipaddress.ip_address(row["address"]).version == 4 for row in rows),
            "ipv6": sum(ipaddress.ip_address(row["address"]).version == 6 for row in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("dat", "ru-srs-source", "private-srs-source", "fixtures"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        rows = read_fixtures(args.fixtures)
        report = validate_matrix(args.dat, {"RU": read_srs_source(args.ru_srs_source),
                                          "PRIVATE": read_srs_source(args.private_srs_source)}, rows)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    text = (f"### Routing fixtures: PASS ({report['fixtures']} addresses)\n\n"
            f"IPv4={report['ipv4']}, IPv6={report['ipv6']}, DIRECT={report['direct']}, PROXY={report['proxy']}. "
            "Partial matrix: missing BY/KZ services and independently verified PROXY IP fixtures. "
            "Official DNS ownership is not a network reachability measurement.\n")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as stream:
            stream.write(text)
    print(text)


if __name__ == "__main__":
    main()
