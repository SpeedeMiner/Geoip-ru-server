#!/usr/bin/env python3
"""Independent strict reader and release envelope. Does not import the builder."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = {"RU": 350_000, "PRIVATE": 2048}
MAX_RU = {4: 64_000_000, 6: 2**111}
MIN_RU_PREFIX = {4: 8, 6: 24}
RELATIVE_BP = {4: 50, 6: 100}  # 0.5%, 1%; apply separately to additions and removals.
FLOOR = {4: 4096, 6: 2**80}


def fields(buf):
    def number(at):
        result = 0
        for n in range(10):
            if at >= len(buf):
                raise ValueError("truncated protobuf varint")
            x = buf[at]
            at += 1
            if n == 9 and x > 1:
                raise ValueError("protobuf varint overflow")
            result |= (x & 127) << (7 * n)
            if x < 128:
                return result, at
        raise ValueError("protobuf varint overflow")

    at = 0
    while at < len(buf):
        key, at = number(at)
        tag, wire = divmod(key, 8)
        if not tag:
            raise ValueError("zero protobuf field")
        if wire == 0:
            item, at = number(at)
        elif wire == 2:
            size, at = number(at)
            if size > len(buf) - at:
                raise ValueError("truncated protobuf field")
            item = buf[at:at+size]
            at += size
        else:
            raise ValueError(f"unexpected protobuf wire type {wire}")
        yield tag, wire, item


def route(cidr):
    seen = {}
    for tag, wire, val in fields(cidr):
        if tag not in (1, 2) or tag in seen or wire != {1: 2, 2: 0}[tag]:
            raise ValueError("invalid or duplicate CIDR field")
        seen[tag] = val
    if 1 not in seen:
        raise ValueError("CIDR missing IP")
    addr = ipaddress.ip_address(seen[1])
    prefix = seen.get(2, 0)
    if not prefix:
        raise ValueError("default route not allowed")
    return ipaddress.ip_network((addr, prefix), strict=True)


def normalize(rows):
    result = []
    for a, z in sorted(rows):
        if result and a <= result[-1][1]:
            raise ValueError("overlapping or duplicate CIDR rows")
        if result and a == result[-1][1] + 1:
            result[-1] = (result[-1][0], z)
        else:
            result.append((a, z))
    return result


def read(path):
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError(f"{path}: DAT byte limit exceeded or empty")
    raw = path.read_bytes()
    result = {}
    for tag, wire, message in fields(raw):
        if (tag, wire) != (1, 2):
            raise ValueError("unexpected GeoIPList field")
        name = None
        networks = []
        reverse_seen = False
        for field, kind, val in fields(message):
            if (field, kind) == (1, 2) and name is None:
                name = bytes(val).decode("ascii")
            elif (field, kind) == (2, 2):
                if len(networks) >= max(MAX_ROWS.values()):
                    raise ValueError("CIDR count exceeded")
                networks.append(route(val))
            elif (field, kind) == (3, 0) and not reverse_seen and val == 0:
                reverse_seen = True
            else:
                raise ValueError("unexpected, duplicate or inverted GeoIP entry field")
        if name not in MAX_ROWS or name in result or not 0 < len(networks) <= MAX_ROWS[name]:
            raise ValueError("unexpected category, duplicate category or CIDR count limit")
        sets = {}
        for family in (4, 6):
            these = [n for n in networks if n.version == family]
            if name == "RU" and any(n.prefixlen < MIN_RU_PREFIX[family] for n in these):
                raise ValueError(f"RU prefix wider than /{MIN_RU_PREFIX[family]} for IPv{family}")
            sets[family] = normalize((int(n.network_address), int(n.broadcast_address)) for n in these)
            if name == "RU" and not 0 < total(sets[family]) <= MAX_RU[family]:
                raise ValueError(f"RU IPv{family} address limit exceeded or empty")
        result[name] = sets
    if set(result) != set(MAX_ROWS):
        raise ValueError("expected exactly RU and PRIVATE")
    for f in (4, 6):
        r = result["RU"][f]
        if total(r) != difference_size(r, result["PRIVATE"][f]):
            raise ValueError("RU overlaps PRIVATE")
    return result, hashlib.sha256(raw).hexdigest()


def total(xs):
    return sum(b-a+1 for a,b in xs)


def difference_size(a, b):
    # Ordered interval sweep, independent of the release builder.
    remain = total(a)
    i = j = 0
    while i < len(a) and j < len(b):
        x, y = a[i]
        s, t = b[j]
        remain -= max(0, min(y, t)-max(x, s)+1)
        if y <= t:
            i += 1
        if t <= y:
            j += 1
    return remain


def validate(candidate, reference, reviewed_sha=""):
    old, _ = read(reference)
    new, sha = read(candidate)
    relative = {}
    for f in (4, 6):
        before, after = old["RU"][f], new["RU"][f]
        limit = max(FLOOR[f], total(before) * RELATIVE_BP[f] // 10_000)
        relative[f] = {"before": total(before), "after": total(after),
                       "added": difference_size(after, before), "removed": difference_size(before, after),
                       "limit": limit}
    # A PRIVATE change can redirect traffic regardless of the RU match. Require explicit review.
    private_changed = old["PRIVATE"] != new["PRIVATE"]
    exceeded = private_changed or any(max(x["added"], x["removed"]) > x["limit"] for x in relative.values())
    print(json.dumps({"candidate_sha256": sha, "private_changed": private_changed,
                      "delta": relative, "needs_review": exceeded}, sort_keys=True), flush=True)
    if exceeded and reviewed_sha != sha:
        raise ValueError("publication delta exceeds bounds; review and explicitly dispatch with the exact candidate SHA-256")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--reviewed-sha256", default="")
    a = p.parse_args()
    validate(a.candidate, a.reference, a.reviewed_sha256)
