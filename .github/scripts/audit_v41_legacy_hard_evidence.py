#!/usr/bin/env python3
"""Read-only evidence audit of legacy v38 hard blocks against published v34/v41 RU sets."""
from __future__ import annotations

import argparse
import csv
import ipaddress
import json
from bisect import bisect_right
from collections import Counter
from pathlib import Path

from build_v41_overlay import intervals, parse_geoip_dat, subtract

LEGACY = "v38-baseline-hard-or-unclassified"
CURRENT_HARD = {"antifilter-ip.lst", "antifilter-subnet.lst", "runetfreedom-static-telegram"}
CURRENT_RESOLVER = "antifilter-ipresolve.lst"


def tagged_networks(path: Path):
    result = []
    for lineno, original in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        prefix, sep, labels = line.partition("#")
        if not sep or not labels.strip().startswith("sources="):
            raise ValueError(f"{path.name}:{lineno}: missing provenance sources")
        net = ipaddress.ip_network(prefix.strip(), strict=True)
        sources = set(labels.strip().removeprefix("sources=").split(","))
        if not sources or "" in sources:
            raise ValueError(f"{path.name}:{lineno}: invalid provenance sources")
        result.append((net, sources))
    if not result:
        raise ValueError(f"{path.name}: no provenance records")
    return result


def effective_networks(path: Path):
    result = set()
    for lineno, original in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = original.partition("#")[0].strip()
        if line:
            try:
                result.add(ipaddress.ip_network(line, strict=True))
            except ValueError as exc:
                raise ValueError(f"{path.name}:{lineno}: {exc}") from exc
    if not result:
        raise ValueError("Empty effective blocked set")
    return result


def address_in_ranges(number: int, ranges, starts):
    i = bisect_right(starts, number) - 1
    return i >= 0 and number <= ranges[i][1]


def count_addresses(ranges):
    return sum(hi - lo + 1 for lo, hi in ranges)


def audit(hard, resolver, effective, v34_ru, v41_ru):
    missing = subtract(intervals(v34_ru, 4), intervals(v41_ru, 4))
    missing_starts = [lo for lo, _ in missing]
    direct_ranges = intervals(v41_ru, 4)
    direct_starts = [lo for lo, _ in direct_ranges]
    effective_ranges = intervals(effective, 4)
    effective_starts = [lo for lo, _ in effective_ranges]
    # Preserve both current and historical DNS provenance, not just membership.
    resolver_by_ip = {}
    for net, tags in resolver:
        if net.version != 4 or net.prefixlen != 32:
            raise ValueError("Resolver feed must be IPv4 /32 only")
        resolver_by_ip.setdefault(int(net.network_address), set()).update(tags)

    rows = []
    for net, tags in hard:
        if LEGACY not in tags or (tags & CURRENT_HARD):
            continue
        if net.version != 4 or net.prefixlen != 32:
            raise ValueError(f"Unclassified legacy-only block is not IPv4 /32: {net}")
        ip = int(net.network_address)
        dns_tags = resolver_by_ip.get(ip, set())
        lost = address_in_ranges(ip, missing, missing_starts)
        blocked = address_in_ranges(ip, effective_ranges, effective_starts)
        now_direct = address_in_ranges(ip, direct_ranges, direct_starts)
        fresh_dns = CURRENT_RESOLVER in dns_tags
        row = {
            "prefix": str(net),
            "in_v34_but_not_v41": "YES" if lost else "NO",
            "still_effective_block": "YES" if blocked else "NO",
            "in_v41_direct": "YES" if now_direct else "NO",
            "current_ip_lst": "NO",
            "current_subnet_lst": "NO",
            "current_resolver": "YES" if fresh_dns else "NO",
            "historical_resolver": "YES" if "v38-historical-ipresolve-only" in dns_tags else "NO",
            "review_priority": "OVERRIDE_REVIEW" if (not blocked and now_direct) else
                "HIGH" if lost and not fresh_dns else "MEDIUM" if lost else "LOW",
            "source_evidence": ",".join(sorted(tags | dns_tags)),
        }
        rows.append(row)

    rows.sort(key=lambda r: int(ipaddress.ip_network(r["prefix"]).network_address))
    counts = Counter(r["review_priority"] for r in rows)
    lost = sum(r["in_v34_but_not_v41"] == "YES" for r in rows)
    no_fresh = sum(r["current_resolver"] == "NO" for r in rows)
    historical_dns = sum(r["historical_resolver"] == "YES" for r in rows)
    outside_effective = sum(r["still_effective_block"] == "NO" for r in rows)
    override_direct = sum(r["review_priority"] == "OVERRIDE_REVIEW" for r in rows)
    return rows, {
        "legacy_only_hard_rows": len(rows),
        "legacy_only_absent_current_resolver": no_fresh,
        "legacy_only_historical_resolver": historical_dns,
        "legacy_only_v34_lost": lost,
        "legacy_only_v34_lost_absent_current_resolver": counts["HIGH"],
        "legacy_only_not_effective": outside_effective,
        "legacy_only_not_effective_and_in_direct": override_direct,
        "v34_only_total_ipv4_addresses": count_addresses(missing),
        "priorities": dict(counts),
        "mode": "audit_only_no_direct_or_block_changes",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("hard", "resolver", "effective", "v34", "v41", "output_dir"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    args = parser.parse_args()
    old, current = parse_geoip_dat(args.v34), parse_geoip_dat(args.v41)
    if set(old) != {"RU", "PRIVATE"} or set(current) != {"RU", "PRIVATE"}:
        parser.error("Expected exactly RU and PRIVATE in both GeoIP protobufs")
    for version in (4, 6):
        if subtract(intervals(old["PRIVATE"], version), intervals(current["PRIVATE"], version)) or subtract(
            intervals(current["PRIVATE"], version), intervals(old["PRIVATE"], version)
        ):
            parser.error(f"PRIVATE IPv{version} differs between published baselines")
    rows, summary = audit(
        tagged_networks(args.hard), tagged_networks(args.resolver),
        effective_networks(args.effective), old["RU"], current["RU"]
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "prefix", "in_v34_but_not_v41", "still_effective_block", "in_v41_direct",
        "current_ip_lst", "current_subnet_lst", "current_resolver",
        "historical_resolver", "review_priority", "source_evidence",
    ]
    with (args.output_dir / "legacy_hard_review.tsv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    with (args.output_dir / "priority_v34_losses.tsv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(r for r in rows if r["in_v34_but_not_v41"] == "YES")
    with (args.output_dir / "legacy_hard_override_review.tsv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(r for r in rows if r["still_effective_block"] == "NO")
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
