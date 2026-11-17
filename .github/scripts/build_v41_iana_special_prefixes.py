#!/usr/bin/env python3
"""Normalize IANA special-purpose CIDRs without inferring unknown reachability."""
import argparse
import csv
import ipaddress
from pathlib import Path
import re

# Lower bounds by family and status, anchored to the published v41 input
# (20/5 IPv4 and 13/9 IPv6). A healthy family cannot hide a truncated other CSV.
MINIMUM_PREFIXES = {4: (15, 4), 6: (10, 6)}

FOOTNOTES = re.compile(r"(?:\s*\[[0-9]+\])+\s*$")


def without_notes(value):
    return FOOTNOTES.sub("", (value or "").strip()).strip()


def read_registry(path, family):
    non_global, globally_reachable = set(), set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream, strict=True)
        for field in ("Address Block", "Globally Reachable"):
            if (rows.fieldnames or []).count(field) != 1:
                raise ValueError(f"unexpected IANA CSV schema: {path}")
        for row in rows:
            status = without_notes(row.get("Globally Reachable")).casefold()
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"{path}:{rows.line_num}: malformed CSV record")
            # Unknown reachability is not False, but its row must still be valid.
            if status not in {"", "n/a", "true", "false"}:
                raise ValueError(f"{path}:{rows.line_num}: unknown reachability {status!r}")
            for field in row["Address Block"].split(","):
                token = without_notes(field)
                try:
                    if "/" not in token:
                        raise ValueError("missing prefix length")
                    net = ipaddress.ip_network(token, strict=True)
                    if net.version != family or net.prefixlen == 0:
                        raise ValueError("wrong family or default route")
                except ValueError as exc:
                    raise ValueError(f"{path}:{rows.line_num}: invalid IPv{family} CIDR {token!r}") from exc
                if status == "true":
                    globally_reachable.add(net)
                elif status == "false":
                    non_global.add(net)
    if not non_global or not globally_reachable:
        raise ValueError(f"{path}: missing IPv{family} reachability rows")
    if non_global & globally_reachable:
        raise ValueError(f"{path}: an exact prefix has conflicting reachability")
    return non_global, globally_reachable


def read_required_registry(path, family):
    non_global, globally_reachable = read_registry(path, family)
    minimum_private, minimum_reachable = MINIMUM_PREFIXES[family]
    if len(non_global) < minimum_private or len(globally_reachable) < minimum_reachable:
        raise ValueError(
            f"{path}: unusually small IPv{family} IANA registry: "
            f"non-global={len(non_global)} (minimum {minimum_private}), "
            f"globally reachable={len(globally_reachable)} (minimum {minimum_reachable})"
        )
    return non_global, globally_reachable


def write_prefixes(path, header, nets):
    rows = sorted(nets, key=lambda n: (n.version, int(n.network_address), n.prefixlen))
    path.write_text(header + "\n" + "".join(f"{net}\n" for net in rows), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ipv4", "ipv6", "private_output", "reachable_output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        private4, public4 = read_required_registry(args.ipv4, 4)
        private6, public6 = read_required_registry(args.ipv6, 6)
        non_global = private4 | private6
        global_exceptions = public4 | public6
        write_prefixes(args.private_output, "# IANA Special-Purpose entries where Globally Reachable=False", non_global)
        write_prefixes(args.reachable_output,
                       "# IANA Special-Purpose entries where Globally Reachable=True; carve-outs from broad special blocks",
                       global_exceptions)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print(f"IANA non-global prefixes: {len(non_global)}")
    print(f"IANA global-reachable exception prefixes: {len(global_exceptions)}")


if __name__ == "__main__":
    main()
