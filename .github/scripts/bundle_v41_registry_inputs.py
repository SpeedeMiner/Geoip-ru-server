#!/usr/bin/env python3
"""Audit-only prototype for retaining exact delegated RIR and IANA registry bytes."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import zlib

MEMBERS = (
    "delegated-afrinic-latest", "delegated-apnic-latest",
    "delegated-arin-extended-latest", "delegated-lacnic-latest",
    "delegated-ripencc-latest", "iana-ipv4-special-registry.csv",
    "iana-ipv6-special-registry.csv",
)
MANIFEST = "registry-inputs.json"
HEADER = ["SOURCE", "LOCAL_FILE", "FETCH_URL", "SHA256", "BYTES", "STATUS"]
MAX_MEMBER = 32 * 1024 * 1024
MAX_PAYLOAD = 128 * 1024 * 1024
MAX_PROVENANCE = 1024 * 1024
SHA = re.compile(r"[0-9a-f]{64}")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_small(path, cap):
    with path.open("rb") as f:
        data = f.read(cap + 1)
    if len(data) > cap:
        raise ValueError(f"{path.name} exceeds limit")
    return data


def metadata(provenance, members=MEMBERS):
    raw = read_small(provenance, MAX_PROVENANCE)
    table = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), delimiter="\t")
    if table.fieldnames != HEADER:
        raise ValueError("unexpected input provenance header")
    rows = {}
    for row in table:
        if row["LOCAL_FILE"] not in members:
            continue
        name = row["LOCAL_FILE"]
        if name in rows or None in row or row["STATUS"] != "downloaded":
            raise ValueError(f"duplicate, malformed or unavailable registry input: {name}")
        if not SHA.fullmatch(row["SHA256"] or "") or not re.fullmatch(r"[0-9]{1,8}", row["BYTES"] or ""):
            raise ValueError(f"invalid size or digest for {name}")
        size = int(row["BYTES"])
        if not 0 < size <= MAX_MEMBER:
            raise ValueError(f"out-of-bounds size for {name}")
        rows[name] = {"size": size, "sha256": row["SHA256"]}
    if rows.keys() != set(members) or sum(r["size"] for r in rows.values()) > MAX_PAYLOAD:
        raise ValueError("registry inputs missing or too large")
    return {"schema": 1, "provenance_sha256": sha(raw), "files": rows}


def manifest_bytes(meta):
    return (json.dumps(meta, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def create(provenance, source, out, *, members=MEMBERS):
    meta = metadata(provenance, members)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=out.parent, prefix=out.name + ".")
    part = Path(name)
    try:
        with os.fdopen(fd, "wb") as f, gzip.GzipFile(filename="", fileobj=f, mode="wb", mtime=0, compresslevel=6) as gz:
            with tarfile.open(fileobj=gz, mode="w|", format=tarfile.USTAR_FORMAT) as tar:
                for key in (MANIFEST, *members):
                    if key == MANIFEST:
                        data = manifest_bytes(meta)
                    else:
                        spec = meta["files"][key]
                        path = source / key
                        if path.is_symlink() or not path.is_file():
                            raise ValueError(f"not a plain source file: {key}")
                        data = read_small(path, spec["size"])
                        if len(data) != spec["size"] or sha(data) != spec["sha256"]:
                            raise ValueError(f"original registry input mismatch: {key}")
                    member = tarfile.TarInfo(key)
                    member.size, member.mode, member.mtime = len(data), 0o644, 0
                    tar.addfile(member, io.BytesIO(data))
        result, _ = checked_members(provenance, part, members=members)
        # No pre-existing output can be overwritten, even after a successful replay.
        os.link(part, out)
    finally:
        part.unlink(missing_ok=True)
    return result


def checked_members(provenance, archive, *, members=MEMBERS):
    meta = metadata(provenance, members)
    expected_manifest = manifest_bytes(meta)
    names = (MANIFEST, *members)
    expected_payload = sum(x["size"] for x in meta["files"].values()) + len(expected_manifest)
    cap = expected_payload + len(names) * 1024 + 10240
    compressed = read_small(archive, min(MAX_PAYLOAD, cap + 1024 * 1024))
    gzip_stream = zlib.decompressobj(wbits=31)
    unpacked = gzip_stream.decompress(compressed, cap + 1)
    if len(unpacked) > cap or not gzip_stream.eof or gzip_stream.unconsumed_tail or gzip_stream.unused_data:
        raise ValueError("invalid or overlong gzip envelope")
    seen = {}
    end = 0
    with tarfile.open(fileobj=io.BytesIO(unpacked), mode="r:") as tar:
        for i, member in enumerate(tar):
            if i >= len(names) or member.name != names[i] or member.type != tarfile.REGTYPE:
                raise ValueError(f"unexpected archive member: {member.name}")
            if (member.mode, member.mtime, member.uid, member.gid, member.uname, member.gname) != (0o644, 0, 0, 0, "", ""):
                raise ValueError(f"unexpected member metadata: {member.name}")
            spec = {"size": len(expected_manifest), "sha256": sha(expected_manifest)} if i == 0 else meta["files"][member.name]
            if member.size != spec["size"] or member.offset != end or member.offset_data != end + 512:
                raise ValueError(f"archive member size mismatch: {member.name}")
            data_end = member.offset_data + member.size
            end = (data_end + 511) // 512 * 512
            data = memoryview(unpacked)[member.offset_data:data_end]
            if len(data) != spec["size"] or sha(data) != spec["sha256"] or any(unpacked[data_end:end]):
                raise ValueError(f"archive member digest mismatch: {member.name}")
            seen[member.name] = data
    if seen.keys() != set(names):
        raise ValueError("bundle missing registry inputs")
    if len(unpacked) % 10240 or len(unpacked) - end < 1024 or any(unpacked[end:]):
        raise ValueError("invalid tar terminator or extra data")
    return {"bundle_sha256": sha(compressed), "bundle_bytes": len(compressed),
            "input_bytes": sum(v["size"] for v in meta["files"].values()), **meta}, seen


def verify(provenance, archive, *, members=MEMBERS):
    result, _ = checked_members(provenance, archive, members=members)
    return result


def restore(provenance, archive, output, *, members=MEMBERS):
    result, files = checked_members(provenance, archive, members=members)
    # Verify every byte before writing. Never touch an existing directory.
    output.mkdir()
    try:
        for name in members:
            with (output / name).open("xb") as f:
                f.write(files[name])
    except OSError:
        shutil.rmtree(output)
        raise
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="mode", required=True)
    build = commands.add_parser("create")
    build.add_argument("provenance", type=Path)
    build.add_argument("source", type=Path)
    build.add_argument("archive", type=Path)
    check = commands.add_parser("verify")
    check.add_argument("provenance", type=Path)
    check.add_argument("archive", type=Path)
    unpack = commands.add_parser("restore")
    unpack.add_argument("provenance", type=Path)
    unpack.add_argument("archive", type=Path)
    unpack.add_argument("output", type=Path)
    p.add_argument("--upstream-catalog", type=Path,
                   help="Use the rolling routing-feed corpus instead of the seven registries")
    a = p.parse_args()
    try:
        members = MEMBERS
        if a.upstream_catalog:
            groups = json.loads(a.upstream_catalog.read_bytes())
            members = tuple(sorted(name for group in groups for name in group["files"])) + ("telegram-official-cidrs.txt",)
            if len(members) != len(set(members)) or any(
                not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", "..", MANIFEST)
                for name in members
            ):
                raise ValueError("invalid or duplicate rolling source member")

        if a.mode == "create":
            result = create(a.provenance, a.source, a.archive, members=members)
        elif a.mode == "restore":
            result = restore(a.provenance, a.archive, a.output, members=members)
        else:
            result = verify(a.provenance, a.archive, members=members)
    except (OSError, ValueError, EOFError, tarfile.TarError, zlib.error) as err:
        p.exit(2, f"registry bundle rejected: {err}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
