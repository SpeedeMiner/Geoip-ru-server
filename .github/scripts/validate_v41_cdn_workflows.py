#!/usr/bin/env python3
"""Check shared ordering and the write scope of v41 CDN recovery."""
from pathlib import Path
import subprocess
import yaml


def validate(workflows):
    production = workflows["geoip-v41.yml"]
    repair = workflows["geoip-v41-cdn-repair.yml"]
    queue = repair.get("concurrency", {})
    if (queue != production.get("concurrency") or queue.get("queue") != "max"
            or queue.get("cancel-in-progress") is not False):
        raise ValueError("CDN repair and production must share a non-replacing queue")
    triggers = repair.get("on", repair.get(True))
    if set(triggers or {}) != {"workflow_dispatch"} or set(repair["jobs"]) != {"repair"}:
        raise ValueError("CDN repair must be a manual-only job")
    job = repair["jobs"]["repair"]
    expected = "github.ref == 'refs/heads/main' && github.event_name == 'workflow_dispatch'"
    if (job.get("if") != expected or repair.get("permissions") != {"contents": "read"}
            or job.get("permissions") != {"contents": "write"}):
        raise ValueError("CDN repair write permissions are not limited to the main job")
    steps = job["steps"]
    if (len(steps) != 2 or steps[0].get("with", {}).get("persist-credentials") is not False
            or steps[1].get("run") != "bash .github/scripts/repair_v41_cdn.sh"):
        raise ValueError("Unexpected checkout or execution step in CDN repair")
    publish = production["jobs"]["publish"]
    if publish.get("if") != "github.ref == 'refs/heads/main' && github.event_name != 'pull_request'":
        raise ValueError("Production CDN delivery must remain fenced by the main publish job")
    steps = publish["steps"]
    ship = next(i for i, s in enumerate(steps) if s.get("name") == "Publish GitHub Release")
    cdn = next(i for i, s in enumerate(steps) if s.get("id") == "cdn_ref")
    if (cdn <= ship or steps[cdn].get("run") != "bash ../.github/scripts/deliver_v41_cdn.sh"
            or steps[cdn].get("continue-on-error")):
        raise ValueError("CDN delivery must occur after the GitHub release, with ref errors fatal")
    rolling = [index for index, step in enumerate(steps)
               if step.get("run", "").endswith("/verify_v41_rolling_release.sh")]
    if any(not ship < index < cdn for index in rolling):
        raise ValueError("Full rolling release read-back must precede CDN delivery")
    for name, workflow in workflows.items():
        for j in workflow["jobs"].values():
            for s in j.get("steps", []):
                if "run" in s and s.get("shell", "bash") == "bash":
                    result = subprocess.run(["bash", "-n"], input=s["run"], text=True,
                                            capture_output=True)
                    if result.returncode:
                        raise ValueError(f"{name}: {s.get('name')}: {result.stderr.strip()}")


def main():
    directory = Path(__file__).resolve().parents[1] / "workflows"
    names = ("geoip-v41.yml", "geoip-v41-cdn-repair.yml")
    validate({name: yaml.safe_load((directory / name).read_bytes()) for name in names})
    print("CDN release ordering, repair write scope, queue and shell syntax verified.")


if __name__ == "__main__":
    main()
