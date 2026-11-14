#!/usr/bin/env python3
"""Reproduce the 2026-11-14 ten-host IPv6 shadow without editing any checkout.

Requires the fixed Actions artifact plus a directory containing any omitted
upstream inputs. Files reused from a different run must match the fixed build's
recorded SHA-256. Output is an audit fixture and must not be published.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from ipaddress import ip_network
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

from validate_v41_publication_bounds import read


SOURCE_COMMIT = "b98980c6181c3bfda35445f345ae83777f7d18f3"
BASELINE_SHA = "2735053560ebd598cbdcd71ccf858806d4b955a17e2eac512a7baf249d43653a"
EXPECTED_SHADOW_SHA = "4517a9b8e4dce647d0c7e43deca49dfed87f687a1cc111a7e006e35fe417495f"
SHADOW_DOC = Path(__file__).resolve().parents[2] / "docs/v41-ipv6-citic-shadow-20261114.json"
PRODUCTION_CAP = 121
SHADOW_CAP = 131
INPUTS = {
    "base_v37_geoip": "OUTPUT_FILE",
    "hydra_geoip": "HYDRA_INPUT",
    "regional_rir_inventory": "RIR_RUKZBY_PREFIX_INPUT",
    "kyoresuas_standard_ipv4": "KY_STANDARD_V4_INPUT",
    "kyoresuas_standard_ipv6": "KY_STANDARD_V6_INPUT",
    "kyoresuas_services_json": "KY_SERVICES_INPUT",
    "w1zardz_direct": "W1ZARDZ_INPUT",
    "hxehex_ipwhitelist": "HXEHEX_IP_INPUT",
    "escapingworm_operator_whitelist": "ESCAPINGWORM_OPERATOR_INPUT",
    "v37_blocked_base": "BLOCKED_IP_INPUT",
    "corporate_company_asn_origin_prefixes": "COMPANY_ASN_PREFIXES",
    "corporate_core_prefixes": "CORE_COMPANY_PREFIXES",
    "shared_infrastructure_prefixes": "SHARED_INFRASTRUCTURE_PREFIXES",
    "regional_origin_prefixes": "REGIONAL_ORIGIN_PREFIXES",
    "blocked_exact_and_legacy": "BLOCKED_IP_EXACT_INPUT",
    "blocked_resolver_only": "BLOCKED_IPRESOLVE_ONLY_INPUT",
    "antifilter_ipsum": "BLOCKED_IPSUM_INPUT",
}
OUTPUTS = {
    "V41_OUTPUT_FILE", "CATEGORY_FILE", "V41_QUALITY_REPORT", "V41_METRICS",
    "V41_PREFIX_PROVENANCE", "V41_BLOCKED_PROVENANCE", "V41_BLOCKED_FILE", "V41_MANIFEST",
}
GATES = (
    "validate_v41_base_artifacts", "build_v41_overlay", "validate_v41_overlay",
    "validate_v41_release_gate", "validate_v41_telegram", "validate_v41_publication_bounds",
)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def frozen_source(repo, path):
    return subprocess.check_output(["git", "-C", str(repo), "show", f"{SOURCE_COMMIT}:{path}"])


def snapshot_source(repo, scratch):
    """Materialize only the fixed Python scripts and local data used by the workflow."""
    names = subprocess.check_output([
        "git", "-C", str(repo), "ls-tree", "-r", "-z", "--name-only", SOURCE_COMMIT,
        "--", ".github/scripts", ".github/data",
    ]).decode().strip("\0").split("\0")
    if not names or names == [""]:
        raise ValueError("frozen source tree is unavailable")
    for name in names:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unexpected source path")
        dst = scratch / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(frozen_source(repo, name))


def locked_inputs(artifact, upstream, manifest, names):
    result = {}
    for key, env in INPUTS.items():
        filename = names[env]
        path = next((p for root in (artifact, upstream) if (p := root / filename).is_file()
                     and digest(p) == manifest["input_sha256"][key]), None)
        if path is None:
            raise ValueError(f"missing SHA-pinned input: {filename}")
        result[env] = path
    return result


def workflow_command(workflow, name, files, official, table):
    start = workflow.index(f"python3 .github/scripts/{name}.py")
    parts = []
    for line in workflow[start:].splitlines():
        line = line.rstrip()
        parts.append(line.removesuffix("\\"))
        if not line.endswith("\\"):
            break
    tokens = shlex.split(" ".join(parts))
    if tokens[:2] != ["python3", f".github/scripts/{name}.py"]:
        raise ValueError(f"unexpected command in frozen workflow: {name}")
    for token in [sys.executable, "-B", *tokens[1:]]:
        if token == "$RUNNER_TEMP/telegram-cidrs.txt":
            yield str(official)
        elif token == ".github/data/v41-reviewed-operator-prefixes.tsv":
            yield str(table)
        elif token.startswith("$"):
            yield str(files[token[1:]])
        else:
            yield token


def validate_fixture(document):
    proof = document["shadow"]
    if (proof["control"]["dat_sha256"] != BASELINE_SHA
            or proof["candidate"]["dat_sha256"] != EXPECTED_SHADOW_SHA
            or proof["fixed_production"]["source_sha"] != SOURCE_COMMIT):
        raise ValueError("fixture does not match frozen replay identity")
    rows = proof["fixture"]["added_table_rows"]
    hosts = [ip_network(x["prefix"]) for x in rows]
    if (len(hosts) != SHADOW_CAP - PRODUCTION_CAP or len(set(hosts)) != len(hosts)
            or any(n.version != 6 or n.prefixlen != 128 or not n.subnet_of(ip_network("2001:ad0:cff::/48"))
                   for n in hosts)
            or any(x["country"] != "RU" or x["origin_asn"] != "AS3327" for x in rows)):
        raise ValueError("fixture contains non-exact or out-of-scope admissions")
    return proof, hosts


def run_case(source, workflow, out, table, artifact, locked, names, official):
    out.mkdir()
    files = {key: locked.get(key, (out if key in OUTPUTS else artifact) / value)
             for key, value in names.items()}
    commands = {g: list(workflow_command(workflow, g, files, official, table)) for g in GATES}
    commands["validate_v41_relative_bounds"] = [
        sys.executable, "-B", ".github/scripts/validate_v41_publication_bounds.py",
        "--candidate", str(files["V41_OUTPUT_FILE"]), "--reference", str(artifact / "geoip_RU.dat"),
    ]
    for name, command in commands.items():
        log = out / (name + ".log")
        with log.open("w") as f:
            completed = subprocess.run(command, cwd=source, stdout=f, stderr=subprocess.STDOUT, check=False)
        if completed.returncode:
            raise ValueError(f"{out.name}/{name} failed; see {log}")
        print(f"{out.name}/{name} PASS", flush=True)
    return files["V41_OUTPUT_FILE"], files["V41_BLOCKED_FILE"]


def verify_exact_delta(reference, candidate, hosts):
    before, baseline = read(reference)
    after, candidate_sha = read(candidate)
    host_points = {int(n.network_address) for n in hosts}
    if baseline != BASELINE_SHA or candidate_sha != EXPECTED_SHADOW_SHA:
        raise ValueError("baseline or shadow DAT does not match the fixed replay")
    if before["PRIVATE"] != after["PRIVATE"] or before["RU"][4] != after["RU"][4]:
        raise ValueError("non-candidate coverage changed")
    # Reconstruct the union directly from independent protobuf-reader intervals.
    merged = []
    for start, end in sorted([*before["RU"][6], *((x, x) for x in host_points)]):
        if merged and start <= merged[-1][1] + 1:
            if start <= merged[-1][1]:
                raise ValueError("candidate address was already DIRECT in the control")
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    if merged != after["RU"][6]:
        raise ValueError("shadow contains a broader or narrower delta than the ten hosts")
    return {"baseline_sha256": baseline, "shadow_sha256": candidate_sha,
            "ipv6_added": sorted(str(x) for x in hosts), "ipv6_removed": 0,
            "ipv4_changed": False, "private_changed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, default=Path.cwd())
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--telegram", type=Path, required=True, help="Exact 14-CIDR official snapshot")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    repo, artifact, upstream, official, out = (x.resolve() for x in (
        args.source_repo, args.artifact, args.upstream, args.telegram, args.output,
    ))
    proof, hosts = validate_fixture(json.loads(SHADOW_DOC.read_text()))
    if digest(artifact / "geoip_RU.dat") != BASELINE_SHA:
        raise ValueError("not the fixed production DAT")
    manifest = json.loads((artifact / "geoip_RU_v41_manifest.json").read_text())
    if manifest["output_sha256"] != BASELINE_SHA:
        raise ValueError("not the fixed production manifest")
    workflow = frozen_source(repo, ".github/workflows/geoip-v41.yml").decode()
    names = dict(re.findall(r"^  ([A-Z_0-9]+): ([^\n]+)$", workflow, re.M))
    locked = locked_inputs(artifact, upstream, manifest, names)
    out.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="v41-citic-shadow-") as work:
        src = Path(work)
        snapshot_source(repo, src)
        data = src / ".github/data"
        base_table = data / "v41-reviewed-operator-prefixes.tsv"
        checks = {
            base_table: manifest["input_sha256"]["reviewed_operator_prefixes"],
            data / "v41-regional-admission-exclusions.tsv": manifest["input_sha256"]["regional_admission_exclusions"],
            data / "v41-telegram-official-cidrs.txt": proof["fresh_telegram_sha256"],
            official: proof["fresh_telegram_sha256"],
        }
        for path, want in checks.items():
            if digest(path) != want:
                raise ValueError(f"fixed input hash mismatch: {path.name}")
        control, control_mask = run_case(src, workflow, out / "control", base_table, artifact, locked, names, official)
        shadow_table = out / "citic-exact-shadow.tsv"
        shadow_table.write_bytes(base_table.read_bytes() + "".join(f"RU\t{x}\tAS3327\n" for x in sorted(hosts)).encode())
        if digest(shadow_table) != proof["candidate_table_sha256"]:
            raise ValueError("shadow table differs from the recorded fixture")
        script = src / ".github/scripts/build_v41_overlay.py"
        text = script.read_text()
        old = f"MAX_REVIEWED_OPERATOR_PREFIXES = {PRODUCTION_CAP}"
        if text.count(old) != 1:
            raise ValueError("unexpected frozen reviewed-prefix limit")
        script.write_text(text.replace(old, f"MAX_REVIEWED_OPERATOR_PREFIXES = {SHADOW_CAP}"))
        candidate, candidate_mask = run_case(src, workflow, out / "candidate", shadow_table, artifact, locked, names, official)
    if control.read_bytes() != (artifact / "geoip_RU.dat").read_bytes():
        raise ValueError("control DAT differs from released artifact")
    if not (candidate_mask.read_bytes() == control_mask.read_bytes() == (artifact / candidate_mask.name).read_bytes()):
        raise ValueError("effective block mask changed")
    result = verify_exact_delta(control, candidate, hosts)
    result["effective_block_mask_sha256"] = digest(candidate_mask)
    (out / "verified-delta.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
