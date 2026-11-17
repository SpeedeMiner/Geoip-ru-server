#!/usr/bin/env python3
"""Check fetched bytes before accepting a mirror, including delegated-file completeness."""
import argparse
from collections import Counter
from datetime import datetime
import ipaddress
from pathlib import Path

from build_rir_rukzby_prefixes import ALLOWED_STATUS, COUNTRIES, parse_resource, utc_today, validate_snapshot_age
from prepare_blocked_sources_v41 import subnet_auto_approved

# Conservative absolute floors from the pinned release and verified publisher
# snapshots, independent of the relative byte-size gate. Count distinct usable
# rows so padding, comments and repeats cannot make a truncated feed pass.
ANTIFILTER_MINIMUM = {"ip": 25000, "subnet": 35}


def validate_not_error_page(path):
    with path.open("rb") as stream:
        head = stream.read(4096).lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if not head or head.startswith((b"<!doctype html", b"<html", b"<head", b"<body", b"<?xml", b"<error")):
        raise ValueError(f"empty or HTML/XML response: {path}")


def validate_rir(path, registry, minimum_records=100):
    header = None
    declared = {}
    counts = Counter()
    asn_units = 0
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
            kind = fields[2].lower()
            if (fields[1].upper() in COUNTRIES and kind in {"ipv4", "ipv6"}
                    and fields[6].lower() in ALLOWED_STATUS):
                try:
                    prefixes = parse_resource(fields[1], kind, fields[3], fields[4])
                except (ValueError, TypeError, OverflowError) as exc:
                    raise ValueError(f"{path}:{number}: invalid regional {kind} resource") from exc
                if not prefixes:
                    raise ValueError(f"{path}:{number}: invalid regional {kind} resource")
            if fields[2].lower() == "asn":
                if not fields[4].isascii() or not fields[4].isdigit() or int(fields[4]) <= 0:
                    raise ValueError(f"{path}:{number}: invalid ASN range size")
                asn_units += int(fields[4])
    if header is None:
        raise ValueError(f"{path}: missing delegated header")
    if expected < minimum_records or sum(counts.values()) != expected:
        raise ValueError(f"{path}: declared record count differs from received data or is too small; "
                         f"declared={expected}, actual={sum(counts.values())}, "
                         f"declared_by_type={dict(sorted(declared.items()))}, actual_by_type={dict(sorted(counts.items()))}, "
                         f"asn_units={asn_units}")
    if not set(counts) <= set(declared) or any(declared[k] != counts[k] for k in declared):
        raise ValueError(f"{path}: per-family summary counts do not match records")
    return sum(counts.values())


def validate_antifilter(path, kind, *, minimum_records=None):
    """Check the two required official raw .lst files, without changing their policy."""
    minimum = ANTIFILTER_MINIMUM[kind] if minimum_records is None else minimum_records
    records = set()
    usable = set()
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, raw in enumerate(stream, 1):
            token = raw.partition("#")[0].strip()
            if not token:
                continue
            try:
                value, slash, bits = token.partition("/")
                if "%" in value or (slash and (not bits.isascii() or not bits.isdecimal())):
                    raise ValueError
                if kind == "ip":
                    address = ipaddress.ip_address(value)
                    if slash and int(bits) != address.max_prefixlen:
                        raise ValueError
                    record = address
                else:
                    if not slash:
                        raise ValueError
                    record = ipaddress.ip_network(token, strict=True)
                    if record.prefixlen == 0:
                        raise ValueError
            except ValueError:
                expected = "exact host IP" if kind == "ip" else "aligned, explicit non-default CIDR"
                raise ValueError(f"{path}:{line_number}: expected {expected}") from None
            records.add(record)
            if kind == "ip" or subnet_auto_approved(record):
                usable.add(record)
    if len(usable) < minimum:
        raise ValueError(f"{path}: only {len(usable)} distinct usable Antifilter {kind} records "
                         f"({len(records)} distinct valid total); minimum={minimum}")
    return len(records), len(usable)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--registry", choices=("afrinic", "apnic", "arin", "lacnic", "ripencc"))
    source.add_argument("--antifilter", choices=tuple(ANTIFILTER_MINIMUM))
    args = parser.parse_args()
    try:
        validate_not_error_page(args.file)
        if args.registry:
            print(f"{args.registry}: validated {validate_rir(args.file, args.registry)} delegated records")
        if args.antifilter:
            valid, usable = validate_antifilter(args.file, args.antifilter)
            print(f"Antifilter {args.antifilter}: {valid} distinct valid records, {usable} usable under existing scope")
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f"invalid upstream: {exc}\n")


if __name__ == "__main__":
    main()
