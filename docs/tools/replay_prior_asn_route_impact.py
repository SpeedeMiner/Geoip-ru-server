#!/usr/bin/env python3
"""Run a local counterfactual v37/v41 build with only the prior RU ASN inventory."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import yaml


def run(tree, output, previous_asn, compiler, reference):
    shutil.copytree(tree, output, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    wf = yaml.load((output / ".github/workflows/geoip-v41.yml").read_text(), Loader=yaml.BaseLoader)
    steps = {s.get("name"): s for s in wf["jobs"]["build"]["steps"]}
    env = {**os.environ, **wf["env"], "PYTHONDONTWRITEBYTECODE": "1", "REPLAY_BUILDER": str(compiler)}
    base_log = output / "counterfactual.log"
    shutil.copyfile(previous_asn, output / env["RU_ASN_REGISTRY"])
    build = steps["Build unified DIRECT GeoIP RU+BY+KZ v37 with curated blocked-destination exclusions"]["run"]
    build = build[build.index("/tmp/geoip-direct-ru-by-kz-v37-builder \\\n"):].replace(
        "/tmp/geoip-direct-ru-by-kz-v37-builder", '"$REPLAY_BUILDER"')
    # This is a counterfactual, not a candidate: do not run any publishing commands.
    with base_log.open("w") as f:
        for cmd in (steps["Extract RU/BY/KZ registered ASN prefixes and global ipverse BGP observation set"]["run"], build):
            subprocess.run(["bash", "-euo", "pipefail", "-c", cmd], cwd=output, env=env,
                           stdout=f, stderr=subprocess.STDOUT, check=True)
    # Compare exact integer ranges, independently of relative policy thresholds.
    sys.path.insert(0, str(output / ".github/scripts"))
    from build_v41_overlay import parse_geoip_dat, intervals, subtract
    a, b = parse_geoip_dat(reference), parse_geoip_dat(output / "geoip_RU.dat")
    diff = {}
    for category in ("RU", "PRIVATE"):
        diff[category] = {}
        for family in (4, 6):
            x, y = intervals(a[category], family), intervals(b[category], family)
            add, remove = subtract(y, x), subtract(x, y)
            import ipaddress
            def netlist(data):
                ip = ipaddress.IPv4Address if family == 4 else ipaddress.IPv6Address
                return [str(net) for start, end in data for net in ipaddress.summarize_address_range(ip(start), ip(end))]
            diff[category][str(family)] = {
                "added_to_counterfactual": sum(end - start + 1 for start, end in add),
                "removed_from_counterfactual": sum(end - start + 1 for start, end in remove),
                "added_cidrs": netlist(add), "removed_cidrs": netlist(remove),
            }
    return {"status": "counterfactual_only", "release_changed": False, "delta": diff}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("tree", "output", "previous_asn", "compiler", "reference"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    print(json.dumps(run(*[getattr(a, n).resolve() for n in ("tree", "output", "previous_asn", "compiler", "reference")]), indent=2))
