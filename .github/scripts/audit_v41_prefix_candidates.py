#!/usr/bin/env python3
"""Report exact candidate-prefix coverage; do not change routes or publish artifacts."""
import argparse
import csv
from datetime import date, datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from validate_v41_publication_bounds import difference_size, read, total

HEADER = ["prefix", "origin_asn", "service", "observed_on", "review_after", "bgp_evidence", "registration_evidence"]


def read_candidates(path, *, as_of=None):
    today = as_of or datetime.now(timezone.utc).date()
    result, seen = [], set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != HEADER:
            raise ValueError("invalid coverage-candidate schema")
        for row in reader:
            if None in row or any(not row.get(k) or row[k] != row[k].strip() for k in HEADER):
                raise ValueError(f"{path}:{reader.line_num}: missing or malformed field")
            net = ipaddress.ip_network(row["prefix"], strict=True)
            if str(net) != row["prefix"] or net.prefixlen == 0 or net in seen:
                raise ValueError(f"{path}:{reader.line_num}: invalid or duplicate prefix")
            seen.add(net)
            if not re.fullmatch(r"AS[1-9][0-9]*", row["origin_asn"]) or int(row["origin_asn"][2:]) > 4294967295:
                raise ValueError(f"{path}:{reader.line_num}: invalid ASN")
            observed, review = date.fromisoformat(row["observed_on"]), date.fromisoformat(row["review_after"])
            if (observed.isoformat() != row["observed_on"] or review.isoformat() != row["review_after"]
                    or observed > today or review < observed):
                raise ValueError(f"{path}:{reader.line_num}: invalid evidence date")
            for key in ("bgp_evidence", "registration_evidence"):
                value = row[key]
                url = urlsplit(value)
                if (url.scheme != "https" or not url.hostname or not url.path or url.username or url.password
                        or url.fragment or any(c.isspace() for c in value)):
                    raise ValueError(f"{path}:{reader.line_num}: invalid evidence URL")
            result.append({**row, "review_due": today > review})
    if not result:
        raise ValueError("coverage candidate list is empty")
    return result


def coverage(categories, rows):
    output = []
    for row in rows:
        net = ipaddress.ip_network(row["prefix"])
        target = [(int(net.network_address), int(net.broadcast_address))]
        size = total(target)
        direct = size - difference_size(target, categories["RU"][net.version])
        private = size - difference_size(target, categories["PRIVATE"][net.version])
        output.append({**row, "total_addresses": str(size), "direct_addresses": str(direct),
                       "private_addresses": str(private), "non_direct_addresses": str(size - direct),
                       "coverage": "FULL" if direct == size else "NONE" if direct == 0 else "PARTIAL"})
    return output


def format_report(rows, digest):
    lines = ["## Reviewed prefix coverage (advisory)", "", f"Candidate DAT SHA-256: `{digest}`.", "",
             "This reports address-set membership, not reachability or permission to add routes.", "",
             "| Prefix | Origin | DIRECT / total | PRIVATE | Coverage | Review due |",
             "|---|---|---:|---:|---|---|"]
    for row in rows:
        lines.append(f"| `{row['prefix']}` | {row['origin_asn']} | {row['direct_addresses']} / {row['total_addresses']} | {row['private_addresses']} | {row['coverage']} | {'yes' if row['review_due'] else 'no'} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        categories, digest = read(args.dat)
        rows = coverage(categories, read_candidates(args.candidates))
        report = {"candidate_sha256": digest, "role": "advisory-no-routing-change", "candidates": rows}
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary = format_report(rows, digest)
        if args.summary:
            with args.summary.open("a", encoding="utf-8") as stream:
                stream.write(summary)
        print(summary)
    except (OSError, ValueError, KeyError, TypeError, csv.Error, json.JSONDecodeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
