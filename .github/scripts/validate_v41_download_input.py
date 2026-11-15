#!/usr/bin/env python3
"""Validate a staged v41 download before it is accepted or recorded."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import zlib

from build_rir_rukzby_prefixes import (
    ALLOWED_STATUS, REGISTRIES, parse_as_of, parse_resource, snapshot_header,
    utc_today, validate_snapshot_age,
)
from build_v41_iana_special_prefixes import read_registry
from prepare_blocked_sources_v41 import (
    is_host, read_feed, subnet_auto_approved, validate_host_feed_counts,
    validate_subnet_feed_counts,
)
from validate_v41_telegram import read_telegram_feed
from verify_v41_ipverse_archive import MAX_BYTES, MIN_AGGREGATED_RECORDS, MIN_BYTES


def validate_delegated(path, registry, as_of):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header = snapshot_header(lines, registry)
    validate_snapshot_age(registry, datetime.strptime(header[5], "%Y%m%d").date(), as_of)
    if not re.fullmatch(r"[0-9]{1,9}", header[3]) or int(header[3]) < 3:
        raise ValueError(f"invalid delegated-stat record count for {registry}")
    required = {"asn", "ipv4", "ipv6"}
    declared = {}
    observed = Counter()
    usable = set()
    for line in lines:
        if not (line := line.strip()) or line.startswith("#"):
            continue
        fields = [x.strip() for x in line.split("|")]
        if fields == header:
            continue
        if len(fields) < 6 or fields[0].lower() != registry or fields[2].lower() not in required:
            raise ValueError(f"unexpected delegated-stat row for {registry}")
        _, country, kind, start, value, summary_marker = fields[:6]
        kind = kind.lower()
        if summary_marker.lower() == "summary" and country == start == "*":
            if kind in declared or not re.fullmatch(r"[0-9]{1,9}", value):
                raise ValueError(f"invalid delegated-stat {kind} summary for {registry}")
            declared[kind] = int(value)
            continue
        if len(fields) < 7:
            raise ValueError(f"incomplete delegated-stat {kind} row for {registry}")
        observed[kind] += 1
        if (kind in usable or not re.fullmatch(r"[A-Z]{2}", country.upper())
                or fields[6].lower() not in ALLOWED_STATUS):
            continue
        try:
            if kind == "asn":
                first, count = int(start), int(value)
                valid = first > 0 and count > 0 and first + count - 1 <= 0xFFFFFFFF
            else:
                valid = bool(parse_resource(country, kind, start, value))
        except (ValueError, OverflowError):
            continue
        if valid:
            usable.add(kind)
    if set(declared) != required or sum(declared.values()) != int(header[3]) or usable != required:
        raise ValueError(f"incomplete delegated-stat header, summaries or records for {registry}")
    for kind, count in declared.items():
        # Retained LACNIC 2026-11-13 publishes fewer ASN rows than it declares.
        # Do not mistreat that upstream convention as IPv4/IPv6 truncation.
        if registry == "lacnic" and kind == "asn" and observed[kind] < count:
            print(f"LACNIC ASN summary differs from observed rows: {observed[kind]} vs {count}; "
                  "IPv4 and IPv6 still require exact counts", file=sys.stderr)
            continue
        if observed[kind] != count:
            raise ValueError(f"incomplete delegated-stat {kind} rows for {registry}: {observed[kind]} != {count}")


class StrictTarInfo(tarfile.TarInfo):
    @classmethod
    def fromtarfile(cls, archive):
        try:
            return super().fromtarfile(archive)
        except (tarfile.InvalidHeaderError, tarfile.TruncatedHeaderError, tarfile.EmptyHeaderError) as exc:
            # TarFile.next may otherwise treat a bad header after a valid one as EOF.
            raise tarfile.ReadError(f"invalid ipverse tar header: {exc}") from exc


class BoundedTarInput:
    """Bound actual expanded bytes, including tar headers, PAX data and padding."""
    def __init__(self, stream, limit):
        self.stream = stream
        self.left = limit

    def read(self, size):
        data = self.stream.read(min(size, self.left + 1))
        self.left -= len(data)
        if self.left < 0:
            raise ValueError("ipverse archive exceeds expanded byte limit")
        return data


def validate_ipverse(path, *, min_bytes=MIN_BYTES, min_records=MIN_AGGREGATED_RECORDS,
                     max_expanded=1024 * 1024 * 1024):
    if not min_bytes <= path.stat().st_size <= MAX_BYTES:
        raise ValueError("invalid compressed size for ipverse archive")
    seen = set()
    with gzip.open(path, "rb") as stream:
        bounded = BoundedTarInput(stream, max_expanded)
        with tarfile.open(fileobj=bounded, mode="r|", bufsize=1 << 18, tarinfo=StrictTarInfo) as archive:
            for index, member in enumerate(archive, 1):
                if index > 1_000_000:
                    raise ValueError("ipverse archive contains too many members")
                parts = PurePosixPath(member.name).parts
                if (not parts or "/" in parts or ".." in parts
                        or not (member.isfile() or member.isdir())):
                    raise ValueError(f"invalid ipverse archive member: {member.name!r}")
                if len(parts) < 3 or parts[-3] != "as" or parts[-1] != "aggregated.json":
                    continue
                if (not member.isfile() or not 0 < member.size <= 16 * 1024 * 1024
                        or not re.fullmatch(r"[1-9][0-9]{0,9}", parts[-2])):
                    raise ValueError(f"invalid ipverse aggregate member: {member.name!r}")
                asn = int(parts[-2])
                if asn > 0xFFFFFFFF or asn in seen:
                    raise ValueError(f"invalid or duplicate ipverse ASN: {asn}")
                with archive.extractfile(member) as record:
                    obj = json.load(record)
                if (not isinstance(obj, dict) or type(obj.get("asn")) is not int or obj["asn"] != asn
                        or not isinstance(obj.get("metadata"), dict)
                        or not isinstance(obj.get("prefixes"), dict)):
                    raise ValueError(f"invalid ipverse JSON schema: {member.name!r}")
                for family in ("ipv4", "ipv6"):
                    prefixes = obj["prefixes"].get(family)
                    if not isinstance(prefixes, list) or any(not isinstance(v, str) for v in prefixes):
                        raise ValueError(f"invalid ipverse {family} array: {member.name!r}")
                seen.add(asn)
            # tarfile stops at the first zero header. Require a complete footer,
            # then drain through the stream to validate tar padding and gzip CRC.
            if archive.fileobj.read(512) != bytes(512):
                raise ValueError("ipverse archive lacks a complete tar footer")
            while data := archive.fileobj.read(1 << 18):
                if any(data):
                    raise ValueError("ipverse archive contains data after the tar footer")
    if len(seen) < min_records:
        raise ValueError(f"ipverse archive has only {len(seen)} unique aggregate records")


def validate(path, profile, as_of):
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError(f"invalid download size for {profile}")
    if profile.startswith("rir:") and profile[4:] in REGISTRIES:
        validate_delegated(path, profile[4:], as_of)
    elif profile in ("iana:4", "iana:6"):
        read_registry(path, int(profile[-1]))
    elif profile == "ipverse":
        validate_ipverse(path)
    elif profile == "telegram":
        read_telegram_feed(path)
    elif re.fullmatch(r"sha256:[0-9a-f]{64}", profile):
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != profile[7:]:
                raise ValueError("pinned input SHA-256 mismatch")
    elif profile in ("antifilter-ip.lst", "antifilter-subnet.lst"):
        nets, lines, invalid = read_feed(path, profile)
        host = profile == "antifilter-ip.lst"
        check = is_host if host else subnet_auto_approved
        unique = set(nets)
        approved = sum(check(net) for net in map(ipaddress.ip_network, unique))
        if host:
            validate_host_feed_counts(profile, approved, len(unique), lines, invalid)
        else:
            validate_subnet_feed_counts(approved, lines, invalid)
    else:
        raise ValueError(f"unknown download validation profile: {profile}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("path", type=Path)
    parser.add_argument("--as-of", type=parse_as_of, default=None)
    args = parser.parse_args()
    try:
        validate(args.path, args.profile, args.as_of or utc_today())
    except (OSError, ValueError, EOFError, tarfile.TarError, csv.Error, zlib.error) as exc:
        parser.exit(1, f"Rejected {args.profile} candidate: {exc}\n")


if __name__ == "__main__":
    main()
