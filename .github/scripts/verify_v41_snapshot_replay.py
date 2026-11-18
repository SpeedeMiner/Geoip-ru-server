#!/usr/bin/env python3
"""Restore verified v41 snapshot inputs or compare a replay's client files, offline."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zlib

from bundle_v41_registry_inputs import (
    BLOCK_MEMBERS, MANIFEST as BUNDLE_MANIFEST, MAX_PROVENANCE, MEMBERS, restore,
)
from v41_release_manifest import (CORE, LEGACY_CORE, LEGACY_SNAPSHOT, MAX_BYTES,
                                  PRIVATE_MRS, SCHEMA, SNAPSHOT, reject_private_mrs)
from verify_v41_ipverse_archive import verify_archive

PROVENANCE = "geoip_RU_input_provenance.tsv"
IPVERSE = "as-ip-blocks.tar.gz"
BUNDLES = ("v41-registry-inputs.tar.gz", "v41-upstream-inputs.tar.gz", "v41-block-inputs.tar.gz")
INPUTS = (PROVENANCE, IPVERSE, *BUNDLES)
CATALOG = ".github/data/v41-upstream-sources.json"
TELEGRAM = "telegram-official-cidrs.txt"
SHA256 = re.compile(r"[0-9a-f]{64}")
SHA1 = re.compile(r"[0-9a-f]{40}")
SCHEMAS = {1: (LEGACY_CORE, LEGACY_SNAPSHOT), SCHEMA: (CORE, SNAPSHOT)}


@contextmanager
def regular_input(path):
    # Do not follow an asset symlink or block on a pipe supplied as an asset.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"not a regular file: {path}")
        yield stream


def hash_file(path, cap, output=None):
    h = hashlib.sha256()
    count = 0
    with regular_input(path) as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            count += len(chunk)
            if count > cap:
                raise ValueError(f"file exceeds its bound: {path.name}")
            h.update(chunk)
            if output is not None:
                output.write(chunk)
    return {"sha256": h.hexdigest(), "bytes": count}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_manifest(path, expected_sha256):
    if not SHA256.fullmatch(expected_sha256):
        raise ValueError("manifest SHA-256 must be 64 lowercase hexadecimal characters")
    with regular_input(path) as stream:
        raw = stream.read(16385)
    if not 0 < len(raw) <= 16384 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("release manifest size or SHA-256 mismatch")
    data = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(data, dict) or type(data.get("schema")) is not int or data["schema"] not in SCHEMAS
            or not SHA1.fullmatch(data.get("source_commit", ""))):
        raise ValueError("unsupported release manifest schema or source commit")
    assets = data.get("assets")
    core, snapshot = SCHEMAS[data["schema"]]
    if not isinstance(assets, dict) or assets.keys() != set(snapshot):
        raise ValueError(f"release manifest asset inventory does not match v41 schema {data['schema']}")
    for name, spec in assets.items():
        cap = MAX_PROVENANCE if name == PROVENANCE else MAX_BYTES
        if (not isinstance(spec, dict) or spec.keys() != {"bytes", "sha256"}
                or type(spec.get("bytes")) is not int or not 0 < spec["bytes"] <= cap
                or not SHA256.fullmatch(spec.get("sha256", ""))):
            raise ValueError(f"invalid release manifest identity: {name}")
    for name in core[::2]:
        expected = f"{assets[name]['sha256']}  {name}\n".encode("ascii")
        sidecar = {"bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()}
        if assets[name + ".sha256sum"] != sidecar:
            raise ValueError(f"release manifest sidecar does not bind {name}")
    return data


def catalog_members(raw):
    if len(raw) > 65536:
        raise ValueError("historical upstream source catalog is too large")
    groups = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(groups, list) or not groups or any(
        not isinstance(group, dict) or not isinstance(group.get("files"), dict) or not group["files"]
        for group in groups
    ):
        raise ValueError("malformed historical upstream source catalog")
    names = tuple(sorted(name for group in groups for name in group["files"])) + (TELEGRAM,)
    reserved = {".", "..", BUNDLE_MANIFEST, *SNAPSHOT, *PRIVATE_MRS}
    if len(names) != len(set(names)) or any(
        name in reserved or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", name) for name in names
    ):
        raise ValueError("invalid or duplicate historical upstream member")
    return names


def read_historical_catalog(source_repo, source_commit):
    # A different checkout/working tree cannot supply the catalog. For partial
    # clones, refuse all Git transports rather than lazily fetching objects.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="", GIT_TERMINAL_PROMPT="0")
    prefix = ["git", "--no-replace-objects", "-c", "protocol.allow=never", "-C", str(source_repo.resolve())]
    def git(*args):
        result = subprocess.run([*prefix, *args], capture_output=True, env=env, timeout=20)
        if result.returncode:
            raise ValueError(f"exact source commit or catalog unavailable locally: {source_commit}")
        return result.stdout
    if git("rev-parse", "--verify", f"{source_commit}^{{commit}}").strip() != source_commit.encode():
        raise ValueError("source identity is not the exact commit named in the manifest")
    object_name = f"{source_commit}:{CATALOG}"
    if not 0 < int(git("cat-file", "-s", object_name)) <= 65536:
        raise ValueError("historical upstream source catalog has invalid size")
    return git("cat-file", "blob", object_name)


def restore_inputs(manifest, inputs, source_repo, output):
    if not inputs.is_dir() or not source_repo.is_dir():
        raise ValueError("input directory and local source repository must exist")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"output path already exists: {output}")
    target = output.resolve()
    if target.is_relative_to(inputs.resolve()) or target.is_relative_to(source_repo.resolve()):
        raise ValueError("output must be outside the input directory and source repository")
    asset_specs = manifest["assets"]
    upstream = catalog_members(read_historical_catalog(source_repo, manifest["source_commit"]))
    member_groups = (MEMBERS, upstream, BLOCK_MEMBERS)
    all_members = (*INPUTS[:2], *(name for group in member_groups for name in group))
    if len(all_members) != len(set(all_members)):
        raise ValueError("archive member names collide across input bundles")

    with tempfile.TemporaryDirectory(prefix=".v41-restore-", dir=target.parent) as temporary:
        work = Path(temporary)
        staged = work / "staged"
        staged.mkdir()
        for name in INPUTS:
            with (staged / name).open("xb") as stream:
                actual = hash_file(inputs / name, asset_specs[name]["bytes"], stream)
            if actual != asset_specs[name]:
                raise ValueError(f"release input mismatch: {name}")
        provenance = staged / PROVENANCE
        with redirect_stdout(sys.stderr):
            verify_archive(provenance, staged / IPVERSE)
        paths = {name: staged / name for name in INPUTS[:2]}
        for archive, members in zip(BUNDLES, member_groups):
            bundle_out = work / archive.removesuffix(".tar.gz")
            restore(provenance, staged / archive, bundle_out, members=members)
            paths.update({name: bundle_out / name for name in members})
        # Publish the local files only after all checks. mkdir refuses even an
        # empty existing directory, unlike renaming over an empty directory.
        target.mkdir(mode=0o700)
        try:
            for name, path in paths.items():
                os.link(path, target / name)
        except OSError:
            shutil.rmtree(target)
            raise
    return sorted(paths)


def compare_client_files(manifest, directory):
    if not directory.is_dir():
        raise ValueError(f"replay directory does not exist: {directory}")
    reject_private_mrs(directory)
    result = {}
    for name in SCHEMAS[manifest["schema"]][0]:
        expected = manifest["assets"][name]
        row = {"expected": expected}
        try:
            actual = hash_file(directory / name, MAX_BYTES)
            row.update(actual=actual, match=actual == expected)
        except (OSError, ValueError) as exc:
            row.update(error=str(exc), match=False)
        result[name] = row
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="Local release manifest")
    parser.add_argument("--manifest-sha256", required=True, help="Independently verified exact manifest digest")
    sub = parser.add_subparsers(dest="action", required=True)
    extract = sub.add_parser("restore-inputs", help="Verify five snapshot assets and restore to a new directory")
    extract.add_argument("--inputs", type=Path, required=True)
    extract.add_argument("--source-repo", type=Path, required=True, help="Local Git repository with the exact historical source commit")
    extract.add_argument("--output", type=Path, required=True)
    compare = sub.add_parser("compare-client", help="Compare the client binaries and sidecars required by this snapshot")
    compare.add_argument("--replay", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest, args.manifest_sha256)
        report = {"action": args.action, "source_commit": manifest["source_commit"],
                  "manifest_sha256": args.manifest_sha256}
        if args.action == "restore-inputs":
            report["restored_files"] = restore_inputs(manifest, args.inputs, args.source_repo, args.output)
            success = True
        else:
            files = compare_client_files(manifest, args.replay)
            report["client_assets"] = files
            success = all(row["match"] for row in files.values())
        report["ok"] = success
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if success else 1
    except (OSError, ValueError, TypeError, EOFError, tarfile.TarError, zlib.error, subprocess.SubprocessError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
