#!/usr/bin/env python3
"""Rebuild v41 from frozen primitive inputs and verified archived RIR tables.

No network or publication commands run. The optional raw-RIR mode additionally
regenerates RIR tables if every original delegated snapshot was recovered.
"""
import argparse
import hashlib
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

import yaml

ZIP_SHA = "257aecb9a9b639273afcdec0b8f2b8f32b0e8c80e5b5ff91c17ffa7a7f0e30e7"
TREE_SHA = "79c00c6a9bb8581c22838ab3bbe1350b832cedc5"
TRACKED = {
    "geoip_RU_v37_base.dat", "geoip_RU.dat", "geoip_RU_v41_blocked_ip_exclusions.txt",
    "geoip_RU_v41_prefix_provenance.tsv", "geoip_RU_v41_blocked_provenance.tsv",
    "geoip_RU_v41_source_metrics.tsv", "geoip_RU_BY_KZ_asn_bgp_prefixes.txt",
    "geoip_RU_global_bgp_prefixes.txt", "geoip_RU_BY_KZ_asn_manifest.txt",
    "geoip_RU_company_asn_manifest.tsv", "geoip_RU_company_asn_bgp_prefixes.txt",
    "geoip_RU_company_asn_core_bgp_prefixes.txt", "geoip_RU_shared_infrastructure_bgp_prefixes.txt",
    "geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt", "geoip_RU_blocked_ip_exclusions.txt",
    "geoip_RU_blocked_ip_exact_and_legacy_hard.txt", "geoip_RU_blocked_ipresolve_resolver_only.txt",
    "geoip_RU_blocked_review_candidates.tsv", "geoip_RU_blocked_sources.sha256",
    "geoip_RU_v37_additional_provenance.tsv", "geoip_RU_source_counts.txt", "geoip_RU_categories.txt",
}
RIR_OUTPUTS = {"geoip_RU_registered_asns.txt", "geoip_BY_KZ_registered_asns.txt",
               "geoip_RU_rir_registered_prefixes.txt", "geoip_RU_BY_KZ_rir_registered_prefixes.tsv"}


def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def git_tree_oid(root):
    def oid(kind, data):
        header = f"{kind} {len(data)}\0".encode("ascii")
        return hashlib.sha1(header + data, usedforsecurity=False).digest()

    entries = []
    for path in root.iterdir():
        name = os.fsencode(path.name)
        if path.is_symlink():
            mode, digest = b"120000", oid("blob", os.fsencode(os.readlink(path)))
        elif path.is_dir():
            name += b"/"
            mode, digest = b"40000", bytes.fromhex(git_tree_oid(path))
        else:
            mode = b"100755" if path.stat().st_mode & 0o111 else b"100644"
            digest = oid("blob", path.read_bytes())
        entries.append((name, mode, digest))
    encoded = b"".join(mode + b" " + name.rstrip(b"/") + b"\0" + digest
                       for name, mode, digest in sorted(entries))
    return oid("tree", encoded).hex()


def exact_provenance(root, primitives, raw_rir):
    src = root / "geoip_RU_input_provenance.tsv"
    with src.open(newline="") as f:
        records = list(csv.DictReader(f, delimiter="\t"))
    verified, skipped = [], []
    for r in records:
        name = r["LOCAL_FILE"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in {".", ".."}:
            raise ValueError(f"invalid source name: {name}")
        if name.startswith("delegated-") and not raw_rir:
            skipped.append(name)
            continue
        p = primitives / name
        if r["STATUS"] != "downloaded" or not p.is_file() or p.stat().st_size != int(r["BYTES"]) or sha(p) != r["SHA256"]:
            raise ValueError(f"original source not verified: {name}")
        shutil.copyfile(p, root / name)
        verified.append(name)
    return verified, skipped


def run(tree, artifact, primitives, compiler, gocache, gopath, out, raw_rir=False):
    if git_tree_oid(tree) != TREE_SHA:
        raise ValueError("the replay requires a fresh archive of the pinned Git source tree")
    if sha(artifact) != ZIP_SHA:
        raise ValueError("wrong Actions artifact")
    with zipfile.ZipFile(artifact) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", n) or n in {".", ".."} for n in names):
            raise ValueError("unexpected ZIP member")
        expected = {name: hashlib.sha256(z.read(name)).hexdigest() for name in TRACKED | RIR_OUTPUTS}
        z.extractall(tree)
    out.mkdir(parents=True, exist_ok=True)
    verified, skipped = exact_provenance(tree, primitives, raw_rir)
    wf = yaml.load((tree / ".github/workflows/geoip-v41.yml").read_text(), Loader=yaml.BaseLoader)
    steps = {s.get("name"): s for s in wf["jobs"]["build"]["steps"]}
    bin_path = out / "geoip-v37-builder"
    env = {**os.environ, **wf["env"], "GOTOOLCHAIN": "local", "GOPROXY": "off",
           "GOPATH": str(gopath), "GOCACHE": str(gocache), "PYTHONDONTWRITEBYTECODE": "1"}
    fmt = subprocess.check_output([str(compiler.parent / "gofmt"), "-l", "main.go", "main_test.go"],
                                  cwd=tree / ".github/scripts/geoip-v37-builder", env=env, text=True)
    if fmt:
        raise ValueError(f"Go formatting differs: {fmt}")
    go_dir = tree / ".github/scripts/geoip-v37-builder"
    with (out / "go.log").open("wb") as log:
        for args in (["version"], ["mod", "verify"], ["test", "-mod=readonly", "./..."],
                     ["build", "-mod=readonly", "-buildvcs=false", "-o", str(bin_path), "."]):
            subprocess.run([str(compiler), *args], cwd=go_dir, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    print("go compiler, dependency checks and builder tests: OK", flush=True)

    def stage(name, cmd):
        with (out / (name + ".log")).open("wb") as log:
            subprocess.run(["bash", "-euo", "pipefail", "-c", cmd], cwd=tree, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        print(name + ": OK", flush=True)

    downloader = (tree / ".github/scripts/download_v41_build_inputs.sh").read_text()
    if raw_rir:
        chunk = downloader.split("python3 .github/scripts/build_v41_rir_legacy_inventory.py", 1)[1].split(
            'download_file "IPVERSE ASN/BGP ARCHIVE"', 1)[0]
        stage("rir_iana", "python3 .github/scripts/build_v41_rir_legacy_inventory.py" + chunk)
    else:
        chunk = downloader.split("python3 .github/scripts/build_v41_iana_special_prefixes.py", 1)[1].split(
            'download_file "IPVERSE ASN/BGP ARCHIVE"', 1)[0]
        stage("iana", "python3 .github/scripts/build_v41_iana_special_prefixes.py" + chunk)
    stage("ipverse_and_asns", steps["Extract RU/BY/KZ registered ASN prefixes and global ipverse BGP observation set"]["run"])
    stage("block_layers", steps["Prepare current and legacy block layers after ASN selection"]["run"])
    builder = steps["Build unified DIRECT GeoIP RU+BY+KZ v37 with curated blocked-destination exclusions"]["run"]
    builder = builder[builder.index("/tmp/geoip-direct-ru-by-kz-v37-builder \\\n"):]
    builder = builder.replace("/tmp/geoip-direct-ru-by-kz-v37-builder", '"$REPLAY_BUILDER"')
    env["REPLAY_BUILDER"] = str(bin_path)
    stage("go_and_overlay", builder)
    stage("validate", steps["Validate v37 base and final v41 RU+BY+KZ DIRECT protobuf"]["run"])
    gate = steps["Enforce current-build v41 hard/DIRECT policy before release publication"]["run"]
    env["GITHUB_STEP_SUMMARY"] = str(out / "summary.txt")
    stage("hard_policy_gate", gate)
    stage("archive_verifier", steps["Verify and retain the exact ipverse build input"]["run"])

    actual = {name: sha(tree / name) for name in expected}
    exact = sorted(name for name in expected if expected[name] == actual[name])
    diff = {name: {"expected": expected[name], "actual": actual[name]} for name in expected if name not in exact}
    evidence = {"source_tree": TREE_SHA, "candidate_sha256": ZIP_SHA, "compiler_version": "go1.26.10",
                "builder_binary_sha256": sha(bin_path), "mode": "raw_rir" if raw_rir else "pinned_derived_rir",
                "verified_raw_inputs": verified, "raw_inputs_not_replayed": skipped, "byte_identical_outputs": exact,
                "different_outputs": diff, "dat_sha256": actual["geoip_RU.dat"],
                "v37_base_sha256": actual["geoip_RU_v37_base.dat"],
                "effective_mask_sha256": actual["geoip_RU_v41_blocked_ip_exclusions.txt"],
                "logs_sha256": {p.stem: sha(p) for p in sorted(out.glob("*.log"))}}
    (out / "result.json").write_text(json.dumps(evidence, indent=2) + "\n")
    if diff:
        raise ValueError(f"frozen outputs differ: {sorted(diff)}")
    return evidence


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("tree", "artifact", "primitives", "compiler", "gocache", "gopath", "out"):
        p.add_argument(name, type=Path)
    p.add_argument("--raw-rir", action="store_true")
    a = p.parse_args()
    args = [getattr(a, n).resolve() for n in ("tree", "artifact", "primitives", "compiler", "gocache", "gopath", "out")]
    print(json.dumps(run(*args, raw_rir=a.raw_rir), indent=2))
