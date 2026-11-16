#!/usr/bin/env python3
"""Gate conspicuous size collapse of every required downloaded input."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

REQUIRED = frozenset({
    "davoyan-geoip.dat", "digne-geoip.dat", "golukon-geoip.dat", "grimbird-geoip.dat",
    "hydra-geoip.dat", "kirill-geoip.dat", "v2fly-geoip.dat", "v2fly-geoip.dat.sha256sum",
    "loyalsoldier-by.dat", "loyalsoldier-private.dat", "loyalsoldier-ru.dat",
    "escapingworm-operator-cidr.txt", "w1zardz-ru-ipv4.txt", "kyoresuas-ru-standard-ipv4.txt",
    "kyoresuas-ru-standard-ipv6.txt", "kyoresuas-services.json", "telegram-official-cidrs.txt",
    "delegated-afrinic-latest", "delegated-apnic-latest", "delegated-arin-extended-latest",
    "delegated-lacnic-latest", "delegated-ripencc-latest", "iana-ipv4-special-registry.csv",
    "iana-ipv6-special-registry.csv", "as-ip-blocks.tar.gz", "antifilter-ip.lst", "antifilter-subnet.lst",
    "geoip_RU_v38_approved_blocked_baseline.txt", "geoip_RU_v38_pinned_antifilter-ip.lst",
    "geoip_RU_v38_pinned_antifilter-ipresolve.lst", "geoip_RU_v38_pinned_antifilter-subnet.lst",
})


def read_provenance(path):
    found = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != ["SOURCE", "LOCAL_FILE", "FETCH_URL", "SHA256", "BYTES", "STATUS"]:
            raise ValueError("unexpected input provenance schema")
        for row in reader:
            name = row.get("LOCAL_FILE")
            if name not in REQUIRED:
                continue
            if (None in row or name in found or row["STATUS"] != "downloaded"
                    or not re.fullmatch(r"[0-9a-f]{64}", row["SHA256"])
                    or not row["BYTES"].isdigit() or int(row["BYTES"]) <= 0):
                raise ValueError(f"invalid or duplicate required provenance: {name}")
            found[name] = int(row["BYTES"])
    if set(found) != REQUIRED:
        raise ValueError(f"missing required provenance: {sorted(REQUIRED - set(found))}")
    return found


def compare(previous, current):
    return [{"file": name, "previous_bytes": previous[name], "current_bytes": current[name],
             "needs_review": current[name] * 2 < previous[name]} for name in sorted(REQUIRED)]


def enforce(rows, report_only=False):
    if any(row["needs_review"] for row in rows) and not report_only:
        raise ValueError("required source size fell below 50% of previous release; repair or explicitly revise the source guard")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("previous", "candidate", "manifest", "dat"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    candidate_sha = hashlib.sha256(args.dat.read_bytes()).hexdigest()
    if (data.get("output_sha256") != candidate_sha
            or data.get("input_provenance_sha256") != hashlib.sha256(args.candidate.read_bytes()).hexdigest()):
        raise ValueError("candidate DAT and source provenance do not match manifest")
    rows = compare(read_provenance(args.previous), read_provenance(args.candidate))
    needs_review = any(row["needs_review"] for row in rows)
    print(json.dumps({"candidate_sha256": candidate_sha, "required_sources": len(rows),
                      "minimum": "50% of previous bytes; structural validation remains mandatory",
                      "needs_review": needs_review, "sources": rows}), flush=True)
    enforce(rows, args.report_only)


if __name__ == "__main__":
    main()
