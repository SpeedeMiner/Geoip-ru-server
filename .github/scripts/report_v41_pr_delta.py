#!/usr/bin/env python3
"""Report candidate versus immutable release; publication independently enforces bounds."""
import argparse
import csv
import json
from pathlib import Path
import re

from build_v41_overlay import intersect, networks_from_intervals, subtract
import validate_v41_publication_bounds as gate
from v41_reviewed_ipv6_admission import RECORD_KEY, verify_reviewed_ipv6_admission_manifest
from v41_direct_admission import ROLE


SOURCES = ("rir-RU", "rir-BY", "rir-KZ", "corporate-company-asn-origins",
           "hydra-direct", "hydra-whitelist")
OPTIONAL_SOURCES = ("static-override",)


def address_scope(ranges, family):
    return {"addresses": str(gate.total(ranges)),
            "cidrs": [str(network) for network in sorted(networks_from_intervals(ranges, family))]}


def exact_delta(candidate, reference, checksum, manifest, reviewed_ipv6, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("expected a full release commit SHA")
    before, old_sha = gate.read(reference)
    after, new_sha = gate.read(candidate)
    with checksum.open("rb") as stream:
        if stream.read(256) != f"{old_sha}  geoip_RU.dat\n".encode("ascii"):
            raise ValueError("release DAT does not match its checksum sidecar")
    policy = json.loads(manifest.read_text(encoding="utf-8"))
    if policy.get("output_sha256") != new_sha:
        raise ValueError("candidate manifest does not bind the DAT")
    reviewed = verify_reviewed_ipv6_admission_manifest(reviewed_ipv6, policy)
    role = policy[RECORD_KEY].get("role")
    if role not in {"geography-review-only", ROLE}:
        raise ValueError("unrecognized reviewed IPv6 geography role")
    direct = {}
    for family in (4, 6):
        old, new = before["RU"][family], after["RU"][family]
        direct[f"ipv{family}"] = {
            "added": address_scope(subtract(new, old), family),
            "removed": address_scope(subtract(old, new), family),
        }
    added6 = subtract(after["RU"][6], before["RU"][6])
    removed6 = subtract(before["RU"][6], after["RU"][6])
    geography = []
    for network, record in sorted(reviewed.items()):
        scope = [(int(network.network_address), int(network.broadcast_address))]
        added, removed = intersect(added6, scope), intersect(removed6, scope)
        if added or removed:
            geography.append({
                "prefix": str(network),
                "origin_asn": record["origin_asn"],
                "assignment_country": record["assignment_country"],
                "added": address_scope(added, 6),
                "removed": address_scope(removed, 6),
            })
    return {
        "schema": 1,
        "mode": "ADVISORY",
        "baseline": {"release_commit": revision, "dat_sha256": old_sha},
        "candidate_dat_sha256": new_sha,
        "private_changed": {f"ipv{f}": before["PRIVATE"][f] != after["PRIVATE"][f] for f in (4, 6)},
        "direct": direct,
        "ipv6_geography": {"role": role,
                           "table_sha256": policy["input_sha256"][RECORD_KEY],
                           "changed_overlaps": geography},
    }


def metrics(path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not {"source_id", "unique_cidrs", "ipv4_addresses", "ipv6_addresses"} <= set(reader.fieldnames or ()):
            raise ValueError(f"invalid metrics schema: {path}")
        rows = {}
        for row in reader:
            key = row["source_id"]
            if key in SOURCES + OPTIONAL_SOURCES:
                if key in rows:
                    raise ValueError(f"duplicate source: {key}")
                rows[key] = tuple(int(row[k]) for k in ("unique_cidrs", "ipv4_addresses", "ipv6_addresses"))
        if not set(SOURCES) <= set(rows):
            raise ValueError(f"missing source metrics: {set(SOURCES) - set(rows)}")
        return rows


def report(candidate, reference, current_metrics, previous_metrics, revision):
    before, _, before_count = gate.read(reference, include_counts=True)
    after, sha, after_count = gate.read(candidate, include_counts=True)
    old, new = metrics(previous_metrics), metrics(current_metrics)
    lines = ["## v41: сравнение с опубликованным release", "",
             f"Reference commit: `{revision}`; candidate SHA-256: `{sha}`.", "",
             "| Семейство | Адресов до | Адресов после | Добавлено | Удалено | CIDR до | CIDR после |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for family in (4, 6):
        a, b = before["RU"][family], after["RU"][family]
        lines.append(f"| IPv{family} | {gate.total(a)} | {gate.total(b)} | {gate.difference_size(b, a)} | "
                     f"{gate.difference_size(a, b)} | {before_count['RU'][family]} | {after_count['RU'][family]} |")
    lines += ["", "### Входы по источникам", "",
              "Числа ниже — объединённое пространство каждого входа до итоговой политики; источники пересекаются и не суммируются.", "",
              "| Источник | CIDR до → после | IPv4 до → после | IPv6 до → после |",
              "|---|---:|---:|---:|"]
    for key in SOURCES:
        lines.append(f"| {key} | {old[key][0]} → {new[key][0]} | {old[key][1]} → {new[key][1]} | {old[key][2]} → {new[key][2]} |")
    for key in OPTIONAL_SOURCES:
        def show(index):
            left = str(old[key][index]) if key in old else "нет данных"
            right = str(new[key][index]) if key in new else "нет данных"
            return f"{left} → {right}"
        lines.append(f"| {key} | {show(0)} | {show(1)} | {show(2)} |")
    lines += ["", "Статические overrides могут пересекаться с корпоративным показателем; отсутствие старой метрики не означает ноль.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("candidate", "reference", "current-metrics", "previous-metrics", "summary",
                 "reference-checksum", "candidate-manifest", "reviewed-ipv6", "exact-output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    try:
        delta = exact_delta(args.candidate, args.reference, args.reference_checksum, args.candidate_manifest,
                            args.reviewed_ipv6, args.revision)
        output = report(args.candidate, args.reference, args.current_metrics, args.previous_metrics, args.revision)
        args.exact_output.write_text(json.dumps(delta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        parser.exit(1, f"Could not generate DIRECT delta: {exc}\n")
    with args.summary.open("a", encoding="utf-8") as stream:
        stream.write(output + "\n")
        stream.write("\nExact CIDRs are in the v41-pr-direct-delta artifact. "
                     "Geographic IPv6 overlaps do not imply reachability.\n")
    print(output, flush=True)
    result = gate.validate(args.candidate, args.reference, enforce_delta=False)
    if result["needs_review"]:
        warning = "Relative publication bounds exceeded: review the exact candidate SHA before publication."
        with args.summary.open("a", encoding="utf-8") as stream:
            stream.write(f"\n**Warning: {warning}**\n")
        print(f"::warning::{warning}")


if __name__ == "__main__":
    main()
