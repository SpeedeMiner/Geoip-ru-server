#!/usr/bin/env python3
"""Build RU+BY+KZ registered address-resource inventory from five RIR snapshots.

Country in delegated stats is a resource-registration signal, not physical location.
Output retains source registry and allocation status for every normalized prefix.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import ipaddress
from collections import Counter
from pathlib import Path

REGISTRIES = ("afrinic", "apnic", "arin", "lacnic", "ripencc")
COUNTRIES = ("RU", "BY", "KZ")
ALLOWED_STATUS = {"allocated", "assigned", "legacy"}


def snapshot_header(lines: list[str], expected_registry: str) -> list[str]:
    for line in lines:
        row = [x.strip() for x in line.lstrip("\ufeff").split("|")]
        if len(row) >= 7 and (row[0] == "2" or row[0].startswith("2.")) and row[1].lower() == expected_registry:
            return row
    raise ValueError(f"missing/mismatched delegated-stat header for {expected_registry}")


def parse_resource(country: str, kind: str, start: str, value: str) -> list[str]:
    if kind == "ipv4":
        first = ipaddress.ip_address(start)
        if first.version != 4:
            return []
        count = int(value)
        if count <= 0 or int(first) + count - 1 > (1 << 32) - 1:
            return []
        last = ipaddress.IPv4Address(int(first) + count - 1)
        return [str(net) for net in ipaddress.summarize_address_range(first, last) if net.prefixlen > 0]
    if kind == "ipv6":
        prefixlen = int(value)
        if not 0 < prefixlen <= 128:
            return []
        net = ipaddress.ip_network(f"{start}/{prefixlen}", strict=False)
        return [str(net)] if net.version == 6 and net.prefixlen > 0 else []
    return []


def build(input_paths: dict[str, Path]) -> tuple[list[dict[str, str]], list[str]]:
    unique: set[tuple[str, str, str, str]] = set()
    counts: Counter[tuple[str, str, str]] = Counter()
    summaries = []
    today = dt.date.today()

    for registry in REGISTRIES:
        path = input_paths[registry]
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
        if not lines:
            raise ValueError(f"empty delegated-stat snapshot: {registry}")
        header = snapshot_header(lines, registry)
        snapshot = dt.datetime.strptime(header[5], "%Y%m%d").date()
        age = (today - snapshot).days
        if age < -1 or age > 14:
            raise ValueError(f"stale/future {registry} snapshot {snapshot} ({age} days old)")
        resources = 0
        generated = 0
        for raw in lines:
            normalized = raw.lstrip("\ufeff").strip()
            if not normalized or normalized.startswith("#"):
                continue
            fields = [field.strip() for field in normalized.split("|")]
            if len(fields) < 7:
                continue
            rir, country, kind, start, value, _date, status = fields[:7]
            country = country.upper()
            kind = kind.lower()
            status = status.lower()
            if rir.lower() != registry or country not in COUNTRIES or kind not in {"ipv4", "ipv6"}:
                continue
            if status not in ALLOWED_STATUS:
                continue
            try:
                prefixes = parse_resource(country, kind, start, value)
            except (ValueError, TypeError, OverflowError):
                continue
            if not prefixes:
                continue
            resources += 1
            generated += len(prefixes)
            for prefix in prefixes:
                unique.add((country, prefix, registry, status))
                counts[(country, kind, status)] += 1
        summaries.append(
            f"{registry}: snapshot={snapshot}; resource_records={resources}; "
            f"CIDR_components={generated}; unique_country_registry_rows="
            f"{sum(1 for row in unique if row[2] == registry)}"
        )

    rows = [
        {"country": country, "prefix": prefix, "registry": registry, "status": status}
        for country, prefix, registry, status in sorted(
            unique,
            key=lambda row: (
                row[0],
                ipaddress.ip_network(row[1]).version,
                int(ipaddress.ip_network(row[1]).network_address),
                ipaddress.ip_network(row[1]).prefixlen,
                row[2],
                row[3],
            ),
        )
    ]
    for country in COUNTRIES:
        families = {}
        for version, kind in ((4, "ipv4"), (6, "ipv6")):
            fam = sorted(
                {row["prefix"] for row in rows if row["country"] == country and ipaddress.ip_network(row["prefix"]).version == version},
                key=lambda p: (int(ipaddress.ip_network(p).network_address), ipaddress.ip_network(p).prefixlen),
            )
            families[kind] = len(fam)
        summaries.append(f"{country}: unique_ipv4_prefixes={families['ipv4']}; unique_ipv6_prefixes={families['ipv6']}")
    return rows, summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for registry in REGISTRIES:
        parser.add_argument(f"--{registry}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    args = parser.parse_args()
    paths = {registry: getattr(args, registry) for registry in REGISTRIES}
    rows, summaries = build(paths)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["country", "prefix", "registry", "status"], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    args.stats.write_text(
        "Generated UTC: " + dt.datetime.now(dt.timezone.utc).isoformat() + "\n"
        + "Rows are resource registration evidence; they do not imply physical geolocation or current BGP reachability.\n"
        + "\n".join(summaries) + "\n"
        + f"Total RU+BY+KZ resource rows: {len(rows)}\n",
        encoding="utf-8",
    )
    print(f"RU+BY+KZ RIR resource rows: {len(rows)}")
    print("\n".join(summaries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
