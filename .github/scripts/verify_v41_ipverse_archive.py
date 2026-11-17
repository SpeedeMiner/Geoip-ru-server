#!/usr/bin/env python3
"""Verify the exact compressed ipverse archive against release input provenance."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import tarfile
from urllib.parse import urlsplit


ARCHIVE = "as-ip-blocks.tar.gz"
MIN_AGGREGATED_RECORDS = 10_000
MIN_BYTES = 5_000_000
MAX_BYTES = 64 * 1024 * 1024
HEADER = ["SOURCE", "LOCAL_FILE", "FETCH_URL", "SHA256", "BYTES", "STATUS"]
SNAPSHOT_TAG_RE = rb"(?:v41\.(?:0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]{1,20}\.[0-9]{1,10})\n"


def archive_record(provenance: Path) -> tuple[str, str, int]:
    with provenance.open(encoding="utf-8", newline="") as stream:
        table = csv.DictReader(stream, delimiter="\t")
        if table.fieldnames != HEADER:
            raise ValueError("unexpected source provenance TSV header")
        rows = [row for row in table if row.get("LOCAL_FILE") == ARCHIVE]
    if len(rows) != 1 or None in rows[0]:
        raise ValueError(f"expected one complete provenance row for {ARCHIVE}")
    row, = rows
    digest, count, url = row["SHA256"], row["BYTES"], row["FETCH_URL"]
    if (row["STATUS"] != "downloaded" or not digest or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not count or not re.fullmatch(r"[0-9]{1,8}", count)):
        raise ValueError(f"invalid downloaded provenance for {ARCHIVE}")
    size = int(count)
    if not MIN_BYTES <= size <= MAX_BYTES:
        raise ValueError(f"invalid compressed size for {ARCHIVE}: {size}")
    split = urlsplit(url or "")
    if (split.scheme != "https" or not split.hostname or split.username or split.password
            or re.search(r"\s", url or "")):
        raise ValueError("archive provenance URL must be a credential-free HTTPS URL")
    return url, digest, size


def verify_archive(provenance: Path, archive: Path) -> None:
    _, expected, size = archive_record(provenance)
    h = sha256()
    total = 0
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            total += len(chunk)
            if total > size:
                raise ValueError("ipverse archive exceeds the recorded compressed size")
            h.update(chunk)
    if total != size:
        raise ValueError(f"ipverse archive size mismatch: {total} != {size}")
    if h.hexdigest() != expected:
        raise ValueError(f"ipverse archive SHA-256 mismatch: {h.hexdigest()} != {expected}")
    with gzip.open(archive, "rb") as stream:
        if not stream.read(1):
            raise ValueError("ipverse archive has no gzip payload")
    print(f"Verified ipverse archive: {total} bytes, SHA256={expected}")


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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--provenance", type=Path, required=True)
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--archive", type=Path)
    modes.add_argument("--source-url", action="store_true")
    modes.add_argument("--snapshot-tag-file", type=Path)
    args = p.parse_args()
    try:
        if args.archive:
            verify_archive(args.provenance, args.archive)
        elif args.source_url:
            print(archive_record(args.provenance)[0])
        else:
            with args.snapshot_tag_file.open("rb") as stream:
                tag = stream.read(257)
            if len(tag) > 256 or not re.fullmatch(SNAPSHOT_TAG_RE, tag):
                raise ValueError("invalid snapshot archive tag in release commit")
            print(tag.decode("ascii"), end="")
    except (OSError, EOFError, ValueError) as exc:
        p.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
