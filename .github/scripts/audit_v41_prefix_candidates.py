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

from audit_v41_direct_provenance import read_cdn_advisory
from validate_v41_publication_bounds import difference_size, read, total
from v41_cdn_ip_advisory import prefix_overlaps, status_line

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


def coverage(categories, rows, advisory_index=None):
    output = []
    for row in rows:
        net = ipaddress.ip_network(row["prefix"])
        target = [(int(net.network_address), int(net.broadcast_address))]
        size = total(target)
        direct = size - difference_size(target, categories["RU"][net.version])
        private = size - difference_size(target, categories["PRIVATE"][net.version])
        output.append({**row, "total_addresses": str(size), "direct_addresses": str(direct),
                       "private_addresses": str(private), "non_direct_addresses": str(size - direct),
                       "coverage": "FULL" if direct == size else "NONE" if direct == 0 else "PARTIAL",
                       "cdn_ip_database_overlaps": (prefix_overlaps(target, net.version, advisory_index)
                                                    if advisory_index is not None else None)})
    return output


def format_report(rows, digest, advisory=None):
    lines = ["## Reviewed prefix coverage (advisory)", "", f"Candidate DAT SHA-256: `{digest}`.", "",
             "This reports address-set membership, not reachability or permission to add routes.", "",
             "| Prefix | Origin | DIRECT / total | PRIVATE | Coverage | Review due | CDN scopes (advisory, addresses) |",
             "|---|---|---:|---:|---|---|---|"]
    for row in rows:
        hits = row['cdn_ip_database_overlaps']
        labels = (', '.join(f"{hit['provider']}: {hit['addresses']}" for hit in hits)
                  if hits else 'No overlap in reported scopes' if hits == [] else 'Unknown')
        lines.append(f"| `{row['prefix']}` | {row['origin_asn']} | {row['direct_addresses']} / {row['total_addresses']} | {row['private_addresses']} | {row['coverage']} | {'yes' if row['review_due'] else 'no'} | {labels} |")
    if advisory is not None:
        lines += ['', status_line(advisory), '',
                  'CDN overlap is measured over the entire reviewed prefix, not just its DIRECT part.']
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--provider-snapshot", type=Path)
    args = parser.parse_args()
    try:
        categories, digest = read(args.dat)
        advisory, index = read_cdn_advisory(args.provider_snapshot)
        rows = coverage(categories, read_candidates(args.candidates), index if advisory['status'] == 'AVAILABLE' else None)
        report = {"candidate_sha256": digest, "role": "advisory-no-routing-change",
                  "cdn_ip_database": advisory, "candidates": rows}
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary = format_report(rows, digest, advisory)
        if args.summary:
            with args.summary.open("a", encoding="utf-8") as stream:
                stream.write(summary)
        print(summary)
    except (OSError, ValueError, KeyError, TypeError, csv.Error, json.JSONDecodeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
