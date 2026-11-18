#!/usr/bin/env python3
"""Build a pair of local mihomo rule-sets only after exact DAT round-trip verification."""

import argparse
import hashlib
import ipaddress
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from build_v41_overlay import collapse, interval_size, intervals, subtract_ranges
from build_v41_srs import check_dat


MRS_NAMES = {"RU": "geoip_RU.mrs", "PRIVATE": "geoip_PRIVATE.mrs"}
# Official MetaCubeX v1.19.34 linux-amd64-compatible, after gzip extraction.
MIHOMO_SHA256 = "5b6644c487e5dffae86b0e0e9bb5cec445579a3a9d03977c09576fee2aeefc01"
ZSTD_MAGIC = bytes.fromhex("28b52ffd")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def convert(mihomo, fmt, source, target):
    # The format argument describes the input. `mrs` input exports plain text.
    subprocess.run([mihomo, "convert-ruleset", "ipcidr", fmt, source, target],
                   check=True, timeout=60)


def verify_coverage(text, networks, name):
    cidrs = text.splitlines()
    if not cidrs or any("/" not in cidr for cidr in cidrs):
        raise ValueError(f"Empty or malformed mihomo CIDR export: {name}")
    try:
        actual = [ipaddress.ip_network(cidr) for cidr in cidrs]
    except ValueError as exc:
        raise ValueError(f"Invalid CIDR in mihomo export: {name}: {exc}") from exc
    differences = []
    for version in (4, 6):
        expected_ranges = intervals(networks, version)
        actual_ranges = intervals(actual, version)
        if expected_ranges != actual_ranges:
            extra = interval_size(subtract_ranges(actual_ranges, expected_ranges))
            missing = interval_size(subtract_ranges(expected_ranges, actual_ranges))
            differences.append(f"IPv{version} +{extra} / -{missing} addresses")
    if differences:
        raise ValueError(f"MRS coverage differs from the Full DAT: {name} ({', '.join(differences)})")


def verify_mrs(mihomo, binary, decompiled, networks):
    with binary.open("rb") as stream:
        if stream.read(len(ZSTD_MAGIC)) != ZSTD_MAGIC:
            raise ValueError(f"Unexpected MRS frame: {binary.name}")
    # The official decoder validates the inner MRS header and ipcidr behavior.
    convert(mihomo, "mrs", binary, decompiled)
    verify_coverage(decompiled.read_text(encoding="ascii"), networks, binary.name)


def compile_and_verify(mihomo, output, categories):
    mihomo = mihomo.resolve(strict=True)
    if digest(mihomo) != MIHOMO_SHA256:
        raise ValueError("mihomo binary SHA-256 does not match the official pinned build")
    with TemporaryDirectory(prefix=".v41-mrs-", dir=output) as directory:
        work = Path(directory)
        results = []
        for category, name in MRS_NAMES.items():
            networks = collapse(categories[category])
            if not networks:
                raise ValueError(f"Empty category {category}")
            source = work / f"{category}.txt"
            source.write_text("".join(f"{net}\n" for net in networks), encoding="ascii")
            binary = work / name
            convert(mihomo, "text", source, binary)
            verify_mrs(mihomo, binary, work / f"{category}.roundtrip.txt", networks)
            sidecar = work / f"{name}.sha256sum"
            sidecar.write_text(f"{digest(binary)}  {name}\n", encoding="ascii")
            results.extend((binary, sidecar))
        for result in results:
            result.replace(output / result.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", type=Path, default=Path("geoip_RU.dat"))
    parser.add_argument("--manifest", type=Path, default=Path("geoip_RU_v41_manifest.json"))
    parser.add_argument("--mihomo", type=Path, required=True,
                        help="Path to the SHA-256 pinned official Linux amd64 binary")
    parser.add_argument("--output", type=Path, required=True, help="Existing output directory")
    args = parser.parse_args()
    try:
        compile_and_verify(args.mihomo, args.output, check_dat(args.full, args.manifest))
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print("Both mihomo rule-sets match the Full DAT IPv4/IPv6 coverage.")


if __name__ == "__main__":
    main()
