#!/usr/bin/env python3
"""Compile the Full DAT categories and verify sing-box address coverage."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from build_v41_overlay import (collapse, intersect, intervals,
                               parse_geoip_dat)


SRS_NAMES = {"RU": "geoip_RU.srs", "PRIVATE": "geoip_PRIVATE.srs"}


def check_dat(path, manifest):
    payload = path.read_bytes()
    document = json.loads(manifest.read_bytes())
    if hashlib.sha256(payload).hexdigest() != document["output_sha256"]:
        raise ValueError(f"GeoIP DAT SHA-256 mismatch: {path.name}")
    categories = parse_geoip_dat(path)
    if set(categories) != set(SRS_NAMES) or not all(categories.values()):
        raise ValueError("Full DAT must contain non-empty RU and PRIVATE categories only")
    for version in (4, 6):
        if intersect(intervals(categories["RU"], version), intervals(categories["PRIVATE"], version)):
            raise ValueError(f"IPv{version} RU and PRIVATE overlap in the Full DAT")
    return categories


def compile_and_verify(sing_box, output, categories):
    with TemporaryDirectory(prefix=".v41-srs-", dir=output) as tmp:
        work = Path(tmp)
        results = []
        for category, name in SRS_NAMES.items():
            networks = categories[category]
            if not networks:
                raise ValueError(f"Empty category {category}")
            source = work / f"{category}.json"
            binary = work / name
            decompiled = work / f"{category}.decompiled.json"
            source.write_text(json.dumps({"version": 1, "rules": [
                {"ip_cidr": [str(net) for net in collapse(networks)]}
            ]}, separators=(",", ":")) + "\n")
            subprocess.run([sing_box, "rule-set", "compile", "--output", str(binary), str(source)], check=True)
            subprocess.run([sing_box, "rule-set", "decompile", "--output", str(decompiled), str(binary)], check=True)
            result = json.loads(decompiled.read_bytes())
            rules = result["rules"]
            if (result["version"] != 1 or len(rules) != 1 or set(rules[0]) != {"ip_cidr"}
                    or not isinstance(rules[0]["ip_cidr"], list)):
                raise ValueError(f"Unexpected decompiled rule structure: {name}")
            actual = [ipaddress.ip_network(cidr) for cidr in rules[0]["ip_cidr"]]
            if any(intervals(actual, v) != intervals(networks, v) for v in (4, 6)):
                raise ValueError(f"SRS coverage differs from the Full DAT: {name}")
            checksum = work / (name + ".sha256sum")
            checksum.write_text(f"{hashlib.sha256(binary.read_bytes()).hexdigest()}  {name}\n")
            results.extend((binary, checksum))
            print(f"{name}: {binary.stat().st_size} bytes, IPv4/IPv6 coverage verified against {category}")
        for file in results:
            file.replace(output / file.name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--full", type=Path, default=Path("geoip_RU.dat"))
    p.add_argument("--manifest", type=Path, default=Path("geoip_RU_v41_manifest.json"))
    p.add_argument("--sing-box", help="Compile and decompile with this binary. Omit for DAT checks only.")
    a = p.parse_args()
    categories = check_dat(a.full, a.manifest)
    if a.sing_box:
        compile_and_verify(a.sing_box, a.full.parent, categories)


if __name__ == "__main__":
    main()
