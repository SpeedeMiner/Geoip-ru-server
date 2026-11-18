#!/usr/bin/env python3
"""Compile or verify the RU-only mihomo export against both the Full DAT and RU SRS."""

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from build_v41_overlay import collapse, interval_size, intervals, subtract_ranges
from build_v41_srs import check_dat
from validate_v41_routing_matrix import read_srs_source
from v41_release_manifest import RU_MRS, reject_private_mrs


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


def verify_coverage(text, networks, name, reference="the Full DAT"):
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
        raise ValueError(f"MRS coverage differs from {reference}: {name} ({', '.join(differences)})")


def verify_mrs(mihomo, binary, decompiled, networks, srs_networks=None):
    with binary.open("rb") as stream:
        if stream.read(len(ZSTD_MAGIC)) != ZSTD_MAGIC:
            raise ValueError(f"Unexpected MRS frame: {binary.name}")
    # The official decoder validates the inner MRS header and ipcidr behavior.
    convert(mihomo, "mrs", binary, decompiled)
    text = decompiled.read_text(encoding="ascii")
    verify_coverage(text, networks, binary.name)
    if srs_networks is not None:
        verify_coverage(text, srs_networks, binary.name, "geoip_RU.srs")


def compile_and_verify(mihomo, output, networks, srs_networks, *, verify_only=False):
    reject_private_mrs(output)
    mihomo = mihomo.resolve(strict=True)
    if digest(mihomo) != MIHOMO_SHA256:
        raise ValueError("mihomo binary SHA-256 does not match the official pinned build")
    networks = collapse(networks)
    if not networks or not srs_networks:
        raise ValueError("Empty RU category in DAT or SRS")
    with TemporaryDirectory(prefix=".v41-mrs-", dir=output) as directory:
        work = Path(directory)
        binary = (output if verify_only else work) / RU_MRS
        sidecar = binary.with_name(f"{RU_MRS}.sha256sum")
        if not verify_only:
            source = work / "ru.txt"
            source.write_text("".join(f"{net}\n" for net in networks), encoding="ascii")
            convert(mihomo, "text", source, binary)
        checksum = f"{digest(binary)}  {RU_MRS}\n".encode("ascii")
        if verify_only and sidecar.read_bytes() != checksum:
            raise ValueError(f"checksum sidecar does not match {RU_MRS}")
        verify_mrs(mihomo, binary, work / "ru.roundtrip.txt", networks, srs_networks)
        if not verify_only:
            sidecar.write_bytes(checksum)
            binary.replace(output / binary.name)
            sidecar.replace(output / sidecar.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", type=Path, default=Path("geoip_RU.dat"))
    parser.add_argument("--manifest", type=Path, default=Path("geoip_RU_v41_manifest.json"))
    parser.add_argument("--mihomo", type=Path, required=True,
                        help="Path to the SHA-256 pinned official Linux amd64 binary")
    parser.add_argument("--sing-box", type=Path, required=True, help="Path to the verified sing-box binary")
    parser.add_argument("--ru-srs", type=Path, default=Path("geoip_RU.srs"))
    parser.add_argument("--output", type=Path, required=True, help="Existing output directory")
    parser.add_argument("--verify-only", action="store_true", help="Validate existing MRS and sidecar")
    parser.add_argument("--metrics", type=Path, help="Augment existing SRS size metrics from this build")
    args = parser.parse_args()
    try:
        networks = check_dat(args.full, args.manifest)["RU"]
        with TemporaryDirectory(prefix="v41-ru-srs-") as directory:
            source = Path(directory) / "ru.json"
            subprocess.run([args.sing_box.resolve(strict=True), "rule-set", "decompile", "--output",
                            source, args.ru_srs], check=True, timeout=60)
            srs_networks = read_srs_source(source)
        compile_and_verify(args.mihomo, args.output, networks, srs_networks, verify_only=args.verify_only)
        if args.metrics is not None:
            metrics = json.loads(args.metrics.read_bytes())
            metrics["categories"]["RU"]["mrs_bytes"] = (args.output / RU_MRS).stat().st_size
            metrics["categories"]["RU"]["mrs_sha256sum_bytes"] = (
                args.output / f"{RU_MRS}.sha256sum").stat().st_size
            args.metrics.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print(f"{RU_MRS}: exact IPv4/IPv6 coverage verified against the Full DAT RU and geoip_RU.srs")


if __name__ == "__main__":
    main()
