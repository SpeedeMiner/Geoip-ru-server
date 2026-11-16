#!/usr/bin/env python3
"""Hold publication on a watched change to DIRECT; never mutate a DAT."""
import argparse
from bisect import bisect_left
from hashlib import sha256
import ipaddress
import json
from pathlib import Path

from validate_v41_publication_bounds import read, total

HEADER = "direction\tprefix\treason"
MAX_TABLE_BYTES = 16_384
MAX_RULES = 64


def load_review_table(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_TABLE_BYTES + 1)
    if len(raw) > MAX_TABLE_BYTES:
        raise ValueError("publication review table is too large")
    lines = raw.decode("utf-8").splitlines()
    if not lines or lines[0] != HEADER or not 1 <= len(lines) - 1 <= MAX_RULES:
        raise ValueError("invalid publication review table header or row count")
    rules = {}
    for number, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        if len(fields) != 3 or not fields[2].strip():
            raise ValueError(f"invalid publication review table row {number}")
        direction, prefix, reason = fields
        net = ipaddress.ip_network(prefix, strict=True)
        if (direction not in {"added", "removed"} or net.version != 4
                or net.prefixlen != 24 or prefix != str(net) or (direction, net) in rules):
            raise ValueError(f"invalid or duplicate publication review table row {number}")
        rules[direction, net] = reason
    return rules, sha256(raw).hexdigest()


def clip(intervals, lower, upper):
    """Get the ordered disjoint intersections with one watched prefix."""
    index = bisect_left(intervals, (lower, -1))
    if index and intervals[index - 1][1] >= lower:
        index -= 1
    out = []
    for i in range(index, len(intervals)):
        a, z = intervals[i]
        if a > upper:
            break
        out.append((max(a, lower), min(z, upper)))
    return out


def subtract(left, right):
    """Return exact disjoint fragments in left but not right (clipped to a /24)."""
    out = []
    j = 0
    for start, stop in left:
        while j < len(right) and right[j][1] < start:
            j += 1
        while j < len(right) and right[j][0] <= stop:
            a, z = right[j]
            if start < a:
                out.append((start, a - 1))
            start = max(start, z + 1)
            if start > stop:
                break
            j += 1
        if start <= stop:
            out.append((start, stop))
    return out


def inspect(candidate, reference, table):
    rules, table_sha = load_review_table(table)
    previous, old_sha = read(reference)
    current, candidate_sha = read(candidate)
    old, new = previous["RU"][4], current["RU"][4]
    changes = []
    for (direction, net), reason in sorted(rules.items()):
        scope = int(net.network_address), int(net.broadcast_address)
        before, after = clip(old, *scope), clip(new, *scope)
        changed = subtract(after, before) if direction == "added" else subtract(before, after)
        if changed:
            cidrs = [str(prefix) for a, z in changed for prefix in
                     ipaddress.summarize_address_range(ipaddress.IPv4Address(a), ipaddress.IPv4Address(z))]
            changes.append({"prefix": str(net), "direction": direction, "addresses": total(changed),
                            "cidrs": cidrs, "reason": reason})
    return {
        "status": "HOLD" if changes else "PASS",
        "reference_sha256": old_sha,
        "candidate_sha256": candidate_sha,
        "review_table_sha256": table_sha,
        "watched_changes": changes,
        "watched_addresses": {direction: sum(x["addresses"] for x in changes if x["direction"] == direction)
                              for direction in ("added", "removed")},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "reference", "table"):
        p.add_argument(f"--{name}", type=Path, required=True)
    a = p.parse_args()
    try:
        result = inspect(a.candidate, a.reference, a.table)
    except (OSError, ValueError) as exc:
        p.exit(1, f"Cannot evaluate scoped publication review: {exc}\n")
    print(json.dumps(result, sort_keys=True), flush=True)
    if result["status"] == "HOLD":
        p.exit(1, "Scoped DIRECT publication review required. Resolve the matching review table rows before retrying.\n")


if __name__ == "__main__":
    main()
