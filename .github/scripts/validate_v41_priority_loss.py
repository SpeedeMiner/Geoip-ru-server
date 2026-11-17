#!/usr/bin/env python3
"""Gate large loss in pre-policy regional inventories and selected ASN origins."""
import argparse
import csv
import hashlib
import ipaddress
import json
from pathlib import Path
import re

from build_v41_overlay import intervals, subtract, interval_size

ASN_RE = re.compile(r"\bAS([0-9]+)\b")
COUNTRIES = ("RU", "BY", "KZ")


def read_asns(path):
    result = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if not re.fullmatch(r"AS[1-9][0-9]*", line) or int(line[2:]) > 4294967295 or int(line[2:]) in result:
            raise ValueError(f"invalid or duplicate priority ASN: {line}")
        result.add(int(line[2:]))
    if not result:
        raise ValueError("empty priority ASN list")
    return result


def read_origins(path, asns):
    result = {f"AS{asn}": set() for asn in asns}
    with path.open(encoding="utf-8") as stream:
        for number, raw in enumerate(stream, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            prefix, sep, labels = line.partition("#")
            if not sep:
                raise ValueError(f"{path}:{number}: missing origin labels")
            selected = {int(value) for value in ASN_RE.findall(labels)} & asns
            if selected:
                net = ipaddress.ip_network(prefix.strip(), strict=True)
                for asn in selected:
                    result[f"AS{asn}"].add(net)
    return result


def read_regions(path):
    result = {country: set() for country in COUNTRIES}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not {"country", "prefix", "registry", "status"} <= set(reader.fieldnames or ()):
            raise ValueError(f"invalid RIR inventory schema: {path}")
        for row in reader:
            if None in row or row["country"] not in COUNTRIES:
                raise ValueError(f"invalid RIR inventory row in {path}")
            result[row["country"]].add(ipaddress.ip_network(row["prefix"], strict=True))
    return result


def compare(previous, candidate):
    rows = []
    for key in sorted(previous):
        if key not in candidate:
            raise ValueError(f"candidate missing {key}")
        for family in (4, 6):
            before, after = intervals(previous[key], family), intervals(candidate[key], family)
            baseline = interval_size(before)
            removed = interval_size(subtract(before, after))
            needs_review = bool(baseline and removed * 10 > baseline)
            rows.append({"group": key, "family": family, "before": str(baseline),
                         "after": str(interval_size(after)), "removed": str(removed),
                         "status": "no-baseline" if not baseline else "review" if needs_review else "ok",
                         "needs_review": needs_review})
        if not previous[key]:
            rows.append({"group": key, "family": 0, "needs_review": True,
                         "reason": "no baseline data; comparison cannot establish coverage"})
    return rows


def verify_binding(manifest_path, dat, origins, rir, company):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    recorded = manifest["input_sha256"]
    if (manifest["output_sha256"] != sha(dat)
            or recorded["regional_rir_inventory"] != sha(rir)
            or recorded["corporate_company_asn_origin_prefixes"] != sha(company)):
        raise ValueError("priority inputs are not bound to candidate manifest")
    matches = re.findall(r"^# selected_origin_input_sha256=([0-9a-f]{64})$",
                         company.read_text(encoding="utf-8"), re.MULTILINE)
    if len(matches) != 1 or matches[0] != sha(origins):
        raise ValueError("selected ASN input does not match the bound company input")


def enforce(rows, digest, reviewed_sha, report_only=False):
    if any(row["needs_review"] for row in rows) and reviewed_sha != digest and not report_only:
        raise ValueError("priority input coverage loss or missing baseline requires exact candidate SHA review")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("candidate-dat", "previous-origins", "candidate-origins", "previous-rir", "candidate-rir", "priority-asns", "manifest", "company-prefixes"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--reviewed-sha256", default="")
    parser.add_argument("--report-only", action="store_true", help="Report without applying the publication gate.")
    args = parser.parse_args()
    verify_binding(args.manifest, args.candidate_dat, args.candidate_origins, args.candidate_rir, args.company_prefixes)
    asns = read_asns(args.priority_asns)
    old = {**read_origins(args.previous_origins, asns), **read_regions(args.previous_rir)}
    new = {**read_origins(args.candidate_origins, asns), **read_regions(args.candidate_rir)}
    rows = compare(old, new)
    digest = hashlib.sha256(args.candidate_dat.read_bytes()).hexdigest()
    report = {"candidate_sha256": digest, "threshold": "removed > 10% of prior address space per family",
              "scope": "input inventories before DIRECT policy; groups may overlap", "rows": rows}
    print(json.dumps(report, ensure_ascii=False), flush=True)
    enforce(rows, digest, args.reviewed_sha256, args.report_only)


if __name__ == "__main__":
    main()
