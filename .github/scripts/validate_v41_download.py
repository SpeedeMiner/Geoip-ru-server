#!/usr/bin/env python3
"""Check fetched bytes before accepting a mirror, including delegated-file completeness."""
import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path

from build_rir_rukzby_prefixes import utc_today, validate_snapshot_age


def validate_not_error_page(path):
    with path.open("rb") as stream:
        head = stream.read(4096).lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if not head or head.startswith((b"<!doctype html", b"<html", b"<head", b"<body", b"<?xml", b"<error")):
        raise ValueError(f"empty or HTML/XML response: {path}")


def validate_rir(path, registry, minimum_records=100):
    header = None
    declared = {}
    counts = Counter()
    with path.open(encoding="utf-8-sig") as stream:
        for number, raw in enumerate(stream, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = [part.strip() for part in line.split("|")]
            if header is None:
                if len(fields) < 7 or not (fields[0] == "2" or fields[0].startswith("2.")) or fields[1].lower() != registry:
                    raise ValueError(f"{path}:{number}: invalid delegated header")
                header = fields
                try:
                    expected = int(header[3])
                    snapshot = datetime.strptime(header[5], "%Y%m%d").date()
                except ValueError as exc:
                    raise ValueError(f"{path}: invalid header count/date") from exc
                validate_snapshot_age(registry, snapshot, utc_today())
                continue
            if len(fields) >= 6 and fields[1] == "*" and fields[5].lower() == "summary":
                kind = fields[2].lower()
                if fields[0].lower() != registry or kind in declared or not fields[4].isdigit():
                    raise ValueError(f"{path}:{number}: invalid summary")
                declared[kind] = int(fields[4])
                continue
            if len(fields) < 7 or fields[0].lower() != registry or fields[2].lower() not in {"asn", "ipv4", "ipv6"}:
                raise ValueError(f"{path}:{number}: malformed resource record")
            counts[fields[2].lower()] += 1
    if header is None:
        raise ValueError(f"{path}: missing delegated header")
    if expected < minimum_records or sum(counts.values()) != expected:
        raise ValueError(f"{path}: declared record count differs from received data or is too small; "
                         f"declared={expected}, actual={sum(counts.values())}, "
                         f"declared_by_type={dict(sorted(declared.items()))}, actual_by_type={dict(sorted(counts.items()))}")
    if not set(counts) <= set(declared) or any(declared[k] != counts[k] for k in declared):
        raise ValueError(f"{path}: per-family summary counts do not match records")
    return sum(counts.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--registry", choices=("afrinic", "apnic", "arin", "lacnic", "ripencc"))
    args = parser.parse_args()
    try:
        validate_not_error_page(args.file)
        if args.registry:
            print(f"{args.registry}: validated {validate_rir(args.file, args.registry)} delegated records")
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f"invalid upstream: {exc}\n")


if __name__ == "__main__":
    main()
