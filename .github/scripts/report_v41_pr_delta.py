#!/usr/bin/env python3
"""Report candidate versus immutable release; publication independently enforces bounds."""
import argparse
import csv
from pathlib import Path

import validate_v41_publication_bounds as gate


SOURCES = ("rir-RU", "rir-BY", "rir-KZ", "corporate-company-asn-origins",
           "hydra-direct", "hydra-whitelist")
OPTIONAL_SOURCES = ("static-override",)


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
    for flag in ("candidate", "reference", "current-metrics", "previous-metrics", "summary"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    output = report(args.candidate, args.reference, args.current_metrics, args.previous_metrics, args.revision)
    with args.summary.open("a", encoding="utf-8") as stream:
        stream.write(output + "\n")
    print(output, flush=True)
    result = gate.validate(args.candidate, args.reference, enforce_delta=False)
    if result["needs_review"]:
        warning = "Relative publication bounds exceeded: review the exact candidate SHA before publication."
        with args.summary.open("a", encoding="utf-8") as stream:
            stream.write(f"\n**Warning: {warning}**\n")
        print(f"::warning::{warning}")


if __name__ == "__main__":
    main()
