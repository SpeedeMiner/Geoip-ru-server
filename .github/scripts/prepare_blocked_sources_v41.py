#!/usr/bin/env python3
"""Prepare v41 blocked exclusions with an immutable v38 fallback snapshot.

The approved v38 combined exclusion set is the fail-safe baseline. New ip.lst and
bounded subnet.lst entries are unioned into it. ipresolve.lst may be unavailable
or empty; in that case its prior approved contents remain carried by the pinned
v38 baseline and the current feed is explicitly marked unavailable, never as a
confirmed zero-block snapshot. Community/Re-filter remain review-only.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

# Curated prefixes explicitly present in runetfreedom/russia-blocked-geoip/config.json
# under ru-blocked / ru-blocked-community. These are kept as exact service prefixes,
# not expanded or summarized by this builder.
TELEGRAM_PREFIXES = (
    "91.105.192.0/23",
    "91.108.4.0/22",
    "91.108.8.0/21",
    "91.108.16.0/21",
    "91.108.56.0/22",
    "95.161.64.0/20",
    "149.154.160.0/20",
    "185.76.151.0/24",
    "2001:67c:4e8::/48",
    "2001:b28:f23c::/47",
    "2001:b28:f23f::/48",
    "2a0a:f280::/32",
)

TOKEN_PREFIXES = ("IP-CIDR6,", "IP-CIDR,", "CIDR,")


def sort_key(value: str) -> tuple[int, int, int]:
    net = ipaddress.ip_network(value, strict=True)
    return net.version, int(net.network_address), net.prefixlen


def parse_line(raw: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    line = raw.strip().lstrip("\ufeff")
    if not line or line.startswith("#"):
        return None
    if "#" in line:
        line = line.split("#", 1)[0].strip()
    upper = line.upper()
    for marker in TOKEN_PREFIXES:
        if upper.startswith(marker):
            line = line[len(marker):].strip()
            break
    # Accept conventional list rows and route-style text. The first token is the
    # actual address/prefix; trailing labels are provenance/metadata.
    token = re.split(r"[\s,;]+", line, maxsplit=1)[0].strip("[](){}\"'")
    if not token:
        return None
    try:
        if "/" in token:
            return ipaddress.ip_network(token, strict=True)
        address = ipaddress.ip_address(token)
        return ipaddress.ip_network(f"{address}/{address.max_prefixlen}", strict=True)
    except ValueError as exc:
        raise ValueError(f"invalid address/prefix {token!r}: {exc}") from exc


def read_feed(path: Path, source: str) -> tuple[list[str], int, int]:
    nets: list[str] = []
    data_lines = 0
    invalid = 0
    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        data_lines += 1
        try:
            net = parse_line(raw)
        except ValueError as exc:
            invalid += 1
            if invalid <= 5:
                print(f"::warning::{source}:{line_no}: {exc}", file=sys.stderr)
            continue
        if net is not None:
            nets.append(net.with_prefixlen)
    return nets, data_lines, invalid


def is_host(net: ipaddress._BaseNetwork) -> bool:
    return net.prefixlen == net.max_prefixlen


def subnet_auto_approved(net: ipaddress._BaseNetwork) -> bool:
    # Match the maximum automatic subnet carve to 65,536 addresses for both
    # families: /16 IPv4 and /112 IPv6. Wide IPv6 allocations are review-only.
    return net.prefixlen >= (16 if net.version == 4 else 112)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip-list", type=Path, required=True)
    parser.add_argument("--ipresolve", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--subnet", type=Path, required=True)
    parser.add_argument("--community", type=Path, required=True)
    parser.add_argument("--refilter", type=Path, required=True)
    parser.add_argument("--approved", type=Path, required=True)
    parser.add_argument("--exact-approved", type=Path, required=True)
    parser.add_argument("--resolved-approved", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--checksums", type=Path, required=True)
    args = parser.parse_args()

    source_paths = {
        "antifilter-ip.lst": args.ip_list,
        "antifilter-ipresolve.lst": args.ipresolve,
        "antifilter-subnet.lst": args.subnet,
        "community-antifilter-community.lst": args.community,
        "re-filter-ipsum.lst": args.refilter,
        "v38-approved-baseline": args.baseline,
    }
    accepted: dict[str, set[str]] = defaultdict(set)
    exact_accepted: dict[str, set[str]] = defaultdict(set)
    resolved_accepted: dict[str, set[str]] = defaultdict(set)
    review: set[tuple[str, str, str]] = set()
    rows: dict[str, dict[str, int]] = {}
    feed_status: dict[str, str] = {source: "AVAILABLE" for source in source_paths}
    telegram_set = set(TELEGRAM_PREFIXES)

    # Carry forward every v38-approved prefix from an immutable, checksum-pinned
    # release snapshot. Reject anything wider than the existing explicit policy.
    source = "v38-approved-baseline"
    nets, lines, invalid = read_feed(source_paths[source], source)
    unique = set(nets)
    if lines < 1000 or not unique:
        raise SystemExit(f"pinned v38 baseline unexpectedly small: lines={lines}, valid_unique={len(unique)}")
    if invalid > max(10, int(lines * 0.001)):
        raise SystemExit(f"pinned v38 baseline has too many invalid rows: {invalid}/{lines}")
    for value in unique:
        net = ipaddress.ip_network(value, strict=True)
        if is_host(net) or subnet_auto_approved(net) or value in telegram_set:
            accepted[value].add(source)
            # v38 combined baseline has no source-level provenance per CIDR.
            # Conservatively retain it as a hard/exact block for every network class.
            exact_accepted[value].add("v38-baseline-unclassified")
        else:
            raise SystemExit(f"unsafe broad prefix in pinned v38 approved baseline: {value}")
    rows[source] = {"data_lines": lines, "valid_unique": len(unique), "approved": len(unique),
                    "review": 0, "invalid": invalid}

    # Exact host-only sources. An empty ipresolve response is not interpreted as
    # evidence that no destinations are blocked: the pinned v38 approved baseline
    # carries forward its previously accepted resolved-IP entries.
    for source in ("antifilter-ip.lst", "antifilter-ipresolve.lst"):
        nets, lines, invalid = read_feed(source_paths[source], source)
        unique = set(nets)
        approved = 0
        review_count = 0
        if source == "antifilter-ipresolve.lst" and lines == 0 and not unique:
            feed_status[source] = "EMPTY_FALLBACK_V38_PINNED_BASELINE"
            print("::warning::Antifilter ipresolve.lst is empty/unavailable; prior approved entries are carried forward from pinned v38 baseline. This is not a zero-block verdict.")
            rows[source] = {"data_lines": 0, "valid_unique": 0, "approved": 0, "review": 0, "invalid": 0}
            continue
        for value in unique:
            net = ipaddress.ip_network(value, strict=True)
            if is_host(net):
                accepted[value].add(source)
                if source == "antifilter-ip.lst":
                    exact_accepted[value].add(source)
                else:
                    resolved_accepted[value].add(source)
                approved += 1
            else:
                review.add((source, value, "non-host prefix in host-IP feed"))
                review_count += 1
        if lines < 1000 or not unique:
            raise SystemExit(f"{source} unexpectedly small: lines={lines}, valid_unique={len(unique)}")
        if invalid > max(10, int(lines * 0.001)):
            raise SystemExit(f"{source} has too many invalid rows: {invalid}/{lines}")
        rows[source] = {"data_lines": lines, "valid_unique": len(unique), "approved": approved,
                        "review": review_count, "invalid": invalid}

    # Explicit network list: allow up to /16 IPv4 and /112 IPv6. Wider prefixes are
    # held for manual review, preventing a very broad entry from wiping out DIRECT.
    source = "antifilter-subnet.lst"
    nets, lines, invalid = read_feed(source_paths[source], source)
    unique = set(nets)
    approved = 0
    review_count = 0
    for value in unique:
        net = ipaddress.ip_network(value, strict=True)
        if subnet_auto_approved(net):
            accepted[value].add(source)
            exact_accepted[value].add(source)
            approved += 1
        else:
            review.add((source, value, "broader than auto-carve threshold (/16 IPv4, /112 IPv6; 65,536 addresses max)"))
            review_count += 1
    if not unique or lines == 0:
        raise SystemExit("antifilter subnet.lst is empty; refusing to publish without the primary network block source")
    if invalid > max(10, int(lines * 0.01)):
        raise SystemExit(f"antifilter subnet.lst has too many invalid rows: {invalid}/{lines}")
    rows[source] = {"data_lines": lines, "valid_unique": len(unique), "approved": approved,
                    "review": review_count, "invalid": invalid}

    # The fixed Telegram routes are explicit service prefixes in RunetFreedom's
    # upstream config. They are tracked separately from the dynamic community feed.
    for value in telegram_set:
        accepted[value].add("runetfreedom-static-telegram")
        exact_accepted[value].add("runetfreedom-static-telegram")
    rows["runetfreedom-static-telegram"] = {
        "data_lines": len(TELEGRAM_PREFIXES), "valid_unique": len(telegram_set),
        "approved": len(telegram_set), "review": 0, "invalid": 0,
    }

    # Community suggestions and Re-filter summaries are diagnostic candidates only.
    # They do not enter `accepted`, even when they are exact host IPs.
    for source in ("community-antifilter-community.lst", "re-filter-ipsum.lst"):
        nets, lines, invalid = read_feed(source_paths[source], source)
        unique = set(nets)
        for value in unique:
            review.add((source, value, "community/summary source; review only, not auto-carved"))
        if lines > 0 and not unique and invalid > 0:
            print(f"::warning::{source} returned no parseable IP prefixes; keeping it review-only and recording {invalid} invalid lines")
        # Candidate feeds are not used for routing decisions. Non-IP content is
        # retained in the invalid counter rather than failing an otherwise valid build.
        rows[source] = {"data_lines": lines, "valid_unique": len(unique), "approved": 0,
                        "review": len(unique), "invalid": invalid}

    # Reject any prefix broader than the explicit allowlist and thresholds.
    for value in accepted:
        net = ipaddress.ip_network(value, strict=True)
        if not is_host(net) and not subnet_auto_approved(net) and value not in telegram_set:
            raise SystemExit(f"unsafe broad prefix accidentally approved: {value}")

    def write_prefix_set(path: Path, header: str, values: dict[str, set[str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            header + "\n" + "".join(
                f"{value} # sources={','.join(sorted(values[value]))}\n"
                for value in sorted(values, key=sort_key)
            ),
            encoding="utf-8",
        )

    write_prefix_set(
        args.approved,
        "# v41 approved blocked destinations: union of exact/legacy and current resolver candidates.",
        accepted,
    )
    write_prefix_set(
        args.exact_approved,
        "# v41 exact/hard blocks: current ip.lst, bounded subnet.lst, Telegram, and all unclassified v38 baseline rows.",
        exact_accepted,
    )
    write_prefix_set(
        args.resolved_approved,
        "# v41 resolver-derived candidates: current Antifilter ipresolve.lst only.",
        resolved_accepted,
    )
    args.review.write_text(
        "SOURCE\tPREFIX\tREASON\n" + "".join(
            f"{source}\t{prefix}\t{reason}\n"
            for source, prefix, reason in sorted(review, key=lambda row: (row[0], sort_key(row[1]), row[2]))
        ),
        encoding="utf-8",
    )

    stats_lines = [
        "SOURCE\tSTATUS\tDATA_LINES\tVALID_UNIQUE_PREFIXES\tAPPROVED_PREFIXES\tREVIEW_PREFIXES\tINVALID_LINES",
    ]
    for source in source_paths:
        row = rows[source]
        stats_lines.append(f"{source}\t{feed_status.get(source, 'AVAILABLE')}\t{row['data_lines']}\t{row['valid_unique']}\t{row['approved']}\t{row['review']}\t{row['invalid']}")
    row = rows["runetfreedom-static-telegram"]
    stats_lines.append(f"runetfreedom-static-telegram\tCURATED\t{row['data_lines']}\t{row['valid_unique']}\t{row['approved']}\t0\t0")
    stats_lines.append(f"TOTAL_APPROVED_UNIQUE\t-\t-\t{len(accepted)}\t{len(accepted)}\t-\t-")
    stats_lines.append(f"TOTAL_REVIEW_ROWS\t-\t-\t-\t0\t{len(review)}\t-")
    args.stats.write_text("\n".join(stats_lines) + "\n", encoding="utf-8")

    checksum_lines = []
    for source, path in source_paths.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {path.name}  source={source}")
    checksum_lines.append(f"{hashlib.sha256(args.approved.read_bytes()).hexdigest()}  {args.approved.name}  normalized=approved-union")
    checksum_lines.append(f"{hashlib.sha256(args.exact_approved.read_bytes()).hexdigest()}  {args.exact_approved.name}  normalized=exact-hard")
    checksum_lines.append(f"{hashlib.sha256(args.resolved_approved.read_bytes()).hexdigest()}  {args.resolved_approved.name}  normalized=resolver-only")
    checksum_lines.append(f"{hashlib.sha256(args.review.read_bytes()).hexdigest()}  {args.review.name}  normalized=review-only")
    args.checksums.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    if len(accepted) < 1000:
        raise SystemExit(f"approved blocked prefix set unexpectedly small: {len(accepted)}")
    print(f"Approved blocked prefixes: {len(accepted)}")
    print(f"Review-only candidates: {len(review)}")
    accepted_source_types = sorted({accepted_source for values in accepted.values() for accepted_source in values})
    print(f"Accepted source types: {', '.join(accepted_source_types)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
