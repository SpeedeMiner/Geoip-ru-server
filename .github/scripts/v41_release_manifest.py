#!/usr/bin/env python3
"""Bind public release files to one checked build and verify downloaded bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import re

CORE = (
    "geoip_RU.dat", "geoip_RU.dat.sha256sum",
    "geoip_RU.srs", "geoip_RU.srs.sha256sum",
    "geoip_PRIVATE.srs", "geoip_PRIVATE.srs.sha256sum",
)
SNAPSHOT = CORE + (
    "geoip_RU_v41_manifest.json", "geoip_RU_quality_report.txt", "geoip_RU_input_provenance.tsv",
    "as-ip-blocks.tar.gz", "v41-registry-inputs.tar.gz", "v41-upstream-inputs.tar.gz",
    "v41-block-inputs.tar.gz",
)
MANIFEST = "geoip_RU_v41_release_manifest.json"
MAX_BYTES = 128 * 1024 * 1024


def describe(path, cap=MAX_BYTES):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            if size > cap:
                raise ValueError(f"oversize asset: {path.name}")
            digest.update(chunk)
    if not size:
        raise ValueError(f"empty asset: {path.name}")
    return {"sha256": digest.hexdigest(), "bytes": size}


def make(root, source_sha, repository, run_id, run_attempt):
    if (not re.fullmatch(r"[0-9a-f]{40}", source_sha)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or not re.fullmatch(r"[1-9][0-9]{0,19}", run_id)
            or not re.fullmatch(r"[1-9][0-9]{0,9}", run_attempt)):
        raise ValueError("invalid workflow build identity")
    files = {name: describe(root / name) for name in SNAPSHOT}
    for name in CORE[::2]:
        check = root / (name + ".sha256sum")
        if check.read_bytes() != f"{files[name]['sha256']}  {name}\n".encode("ascii"):
            raise ValueError(f"checksum sidecar does not match {name}")
    policy = json.loads((root / "geoip_RU_v41_manifest.json").read_bytes())
    if (policy.get("output_sha256") != files["geoip_RU.dat"]["sha256"]
            or policy.get("input_provenance_sha256") != files["geoip_RU_input_provenance.tsv"]["sha256"]):
        raise ValueError("policy manifest does not bind the DAT and input provenance")
    return {
        "schema": 1,
        "source_commit": source_sha,
        "workflow_run": f"https://github.com/{repository}/actions/runs/{run_id}",
        "run_attempt": int(run_attempt),
        "assets": files,
    }


def verify(root, manifest, names):
    with manifest.open("rb") as f:
        raw = f.read(16385)
    if len(raw) > 16384:
        raise ValueError("oversized release manifest")
    data = json.loads(raw)
    if data.get("schema") != 1 or set(data.get("assets", {})) != set(SNAPSHOT):
        raise ValueError("invalid release manifest")
    for name in names:
        expected = data["assets"][name]
        cap = expected.get("bytes")
        if type(cap) is not int or not 0 < cap <= MAX_BYTES:
            raise ValueError(f"invalid byte count for {name}")
        if describe(root / name, cap=cap) != expected:
            raise ValueError(f"release asset mismatch: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("directory", type=Path)
    create.add_argument("--source-sha", required=True)
    create.add_argument("--repository", required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--run-attempt", required=True)
    check = sub.add_parser("verify")
    check.add_argument("directory", type=Path)
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--core-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "create":
            document = make(args.directory, args.source_sha, args.repository, args.run_id, args.run_attempt)
            with (args.directory / MANIFEST).open("x", encoding="utf-8") as f:
                f.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
        else:
            verify(args.directory, args.manifest, CORE if args.core_only else SNAPSHOT)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
