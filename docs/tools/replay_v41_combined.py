"""Replay the Python stages of v41 using an Actions candidate as frozen input."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

import yaml

EXPECTED_ZIP = "257aecb9a9b639273afcdec0b8f2b8f32b0e8c80e5b5ff91c17ffa7a7f0e30e7"
OUTPUTS = ["geoip_RU.dat", "geoip_RU_v41_blocked_ip_exclusions.txt",
           "geoip_RU_v41_prefix_provenance.tsv", "geoip_RU_v41_blocked_provenance.tsv",
           "geoip_RU_v41_source_metrics.tsv", "as-ip-blocks.tar.gz"]
SELECTED = {
    "base": ("Validate v37 base and final v41 RU+BY+KZ DIRECT protobuf", "validate_v41_base_artifacts.py"),
    "overlay": ("Build unified DIRECT GeoIP RU+BY+KZ v37 with curated blocked-destination exclusions", "build_v41_overlay.py"),
    "validate_overlay": ("Validate v37 base and final v41 RU+BY+KZ DIRECT protobuf", "validate_v41_overlay.py"),
    "release_gate": ("Enforce current-build v41 hard/DIRECT policy before release publication", "validate_v41_release_gate.py"),
    "telegram": ("Verify final DIRECT against the full official Telegram feed", "validate_v41_telegram.py"),
    "bounds": ("Verify absolute publication bounds independently", "validate_v41_publication_bounds.py"),
    "ipverse": ("Verify and retain the exact ipverse build input", "verify_v41_ipverse_archive.py"),
}


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def command(step, script):
    pattern = re.compile(r"^python3 \.github/scripts/" + re.escape(script) + r"[^\n]*(?:\n|$)")
    lines = iter(step["run"].splitlines())
    for line in lines:
        if pattern.match(line):
            found = [line]
            while found[-1].endswith("\\"):
                found.append(next(lines))
            return "\n".join(found)
    raise ValueError(script)


def run(tree, candidate, output, reference, official_feed=None):
    if digest(candidate) != EXPECTED_ZIP:
        raise ValueError("candidate ZIP is not the checked artifact")
    with zipfile.ZipFile(candidate) as z:
        members = z.namelist()
        if len(set(members)) != len(members) or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", n) for n in members):
            raise ValueError("unexpected candidate archive member")
        z.extractall(tree)
    workflow = yaml.load((tree / ".github/workflows/geoip-v41.yml").read_text(), Loader=yaml.BaseLoader)
    steps = {s.get("name"): s for s in workflow["jobs"]["build"]["steps"]}
    env = {**os.environ, **workflow["env"], "PYTHONDONTWRITEBYTECODE": "1"}
    frozen = {n: digest(tree / n) for n in OUTPUTS}
    if digest(reference) != frozen["geoip_RU.dat"]:
        raise ValueError("public DAT does not match frozen DAT")
    cmds = {name: command(steps[step], script) for name, (step, script) in SELECTED.items()}
    if official_feed:
        env["REPLAY_TELEGRAM_FEED"] = str(official_feed.resolve())
        cmds["telegram"] = cmds["telegram"].replace('"$RUNNER_TEMP/telegram-cidrs.txt"', '"$REPLAY_TELEGRAM_FEED"')
    else:
        cmds["telegram"] = cmds["telegram"].replace(' --official-feed "$RUNNER_TEMP/telegram-cidrs.txt"', "")
    env["REPLAY_RELEASE_DAT"] = str(reference.resolve())
    cmds["bounds"] = cmds["bounds"].replace('--reference "$V41_OUTPUT_FILE"', '--reference "$REPLAY_RELEASE_DAT"')
    order = ("base", "overlay", "validate_overlay", "release_gate", "telegram", "bounds", "ipverse")
    output.mkdir(parents=True, exist_ok=True)
    for name in order:
        args = ["bash", "-euo", "pipefail", "-c", cmds[name]]
        done = subprocess.run(args, env=env, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / f"{name}.log").write_bytes(done.stdout)
        print(f"{name}: {done.returncode}", flush=True)
        done.check_returncode()
    actual = {n: digest(tree / n) for n in OUTPUTS}
    if actual != frozen:
        raise ValueError("replay changed tracked DAT, mask, provenance, source metrics or archive")
    return {"input_candidate_sha256": EXPECTED_ZIP, "scope": "frozen v37 base and candidate inputs; Python v41 replay",
            "passed": list(order), "telegram_feed": "fresh download" if official_feed else "repo pin",
            "byte_identical": actual, "logs_sha256": {n: digest(output / f"{n}.log") for n in order}}


if __name__ == "__main__":
    tree, candidate, output, reference, *feed = map(Path, sys.argv[1:])
    evidence = run(tree.resolve(), candidate.resolve(), output.resolve(), reference.resolve(), *feed)
    (output / "result.json").write_text(json.dumps(evidence, indent=2) + "\n")
