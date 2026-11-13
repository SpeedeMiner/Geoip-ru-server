#!/usr/bin/env python3
"""Check every official Telegram CIDR against the independently decoded RU DAT."""
import argparse
import ipaddress
from pathlib import Path

from validate_v41_publication_bounds import difference_size, read, total

PINNED_FEED = Path(__file__).resolve().parent.parent / "data/v41-telegram-official-cidrs.txt"


def read_telegram_feed(path: Path) -> set:
    raw = path.read_bytes()
    if not 0 < len(raw) <= 16384:
        raise ValueError(f"{path}: invalid Telegram feed size")
    nets = set()
    for line in raw.decode("ascii").splitlines():
        if not line:
            continue
        net = ipaddress.ip_network(line, strict=True)
        if (line != str(net) or net in nets or not net.is_global or net.is_multicast
                or net.prefixlen < (16 if net.version == 4 else 24)):
            raise ValueError(f"{path}: invalid, duplicate or excessively broad Telegram CIDR: {line}")
        nets.add(net)
    if {n.version for n in nets} != {4, 6}:
        raise ValueError(f"{path}: Telegram feed must contain both IPv4 and IPv6")
    return nets


def assert_disjoint(dat: Path, telegram: set) -> None:
    categories, _ = read(dat)
    for version in (4, 6):
        ru = categories["RU"][version]
        for n in sorted(n for n in telegram if n.version == version):
            scope = [(int(n.network_address), int(n.broadcast_address))]
            size = total(scope) - difference_size(scope, ru)
            if size:
                raise ValueError(f"RU intersects official Telegram prefix {n}: {size} address(es)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--geoip", type=Path)
    p.add_argument("--official-feed", type=Path)
    a = p.parse_args()
    if not (a.geoip or a.official_feed):
        p.error("provide --geoip, --official-feed, or both")
    try:
        pinned = read_telegram_feed(PINNED_FEED)
        if a.official_feed:
            official = read_telegram_feed(a.official_feed)
            if official != pinned:
                added = ", ".join(sorted(map(str, official - pinned))) or "-"
                removed = ", ".join(sorted(map(str, pinned - official))) or "-"
                raise ValueError(f"official Telegram feed changed (added: {added}; removed: {removed}); review the pinned snapshot")
        if a.geoip:
            assert_disjoint(a.geoip, pinned)
        print(f"Telegram check: PASS ({len(pinned)} CIDRs)")
    except (OSError, ValueError) as exc:
        p.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
