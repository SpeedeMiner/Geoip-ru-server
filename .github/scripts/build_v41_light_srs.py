#!/usr/bin/env python3
"""Compile the Light DAT categories and verify sing-box address coverage."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from build_v41_overlay import (collapse, intersect, interval_size, intervals,
                               parse_geoip_dat, subtract)


SRS_NAMES = {"RU": "geoip_RU_light.srs", "PRIVATE": "geoip_PRIVATE.srs"}


def check_dat(full, light, manifest):
    document = json.loads(manifest.read_bytes())
    light_info = document["light_output"]
    for path, info in ((full, document["output_sha256"]), (light, light_info["sha256"])):
        if hashlib.sha256(path.read_bytes()).hexdigest() != info:
            raise ValueError(f"GeoIP DAT SHA-256 mismatch: {path.name}")
    f, l = parse_geoip_dat(full), parse_geoip_dat(light)
    if set(f) != set(SRS_NAMES) or set(l) != set(SRS_NAMES) or l["PRIVATE"] != f["PRIVATE"]:
        raise ValueError("Light DAT must have exactly RU and unchanged PRIVATE")
    for version in (4, 6):
        a, b = intervals(f["RU"], version), intervals(l["RU"], version)
        if (subtract(b, a) or intersect(b, intervals(l["PRIVATE"], version))
                or interval_size(subtract(a, b)) != light_info["removed_address_space"][f"ipv{version}"]):
            raise ValueError(f"Invalid IPv{version} Light DAT coverage")
    return l


def compile_and_verify(sing_box, output, categories):
    with TemporaryDirectory(prefix=".v41-light-srs-", dir=output) as tmp:
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
                raise ValueError(f"SRS coverage differs from the Light DAT: {name}")
            checksum = work / (name + ".sha256sum")
            checksum.write_text(f"{hashlib.sha256(binary.read_bytes()).hexdigest()}  {name}\n")
            results.extend((binary, checksum))
            print(f"{name}: {binary.stat().st_size} bytes, IPv4/IPv6 coverage verified against {category}")
        for file in results:
            file.replace(output / file.name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--full", type=Path, default=Path("geoip_RU.dat"))
    p.add_argument("--light", type=Path, default=Path("geoip_RU_light.dat"))
    p.add_argument("--manifest", type=Path, default=Path("geoip_RU_v41_manifest.json"))
    p.add_argument("--sing-box", help="Compile and decompile with this binary. Omit for DAT checks only.")
    a = p.parse_args()
    categories = check_dat(a.full, a.light, a.manifest)
    if a.sing_box:
        compile_and_verify(a.sing_box, a.light.parent, categories)


if __name__ == "__main__":
    main()
