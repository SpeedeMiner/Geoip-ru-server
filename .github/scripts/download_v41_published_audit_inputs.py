#!/usr/bin/env python3
"""Download and SHA256-check current published v41 files for a post-release audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

RELEASE = "https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v41/"
INPUTS = {
    "geoip_RU.dat": ("v41.dat", "output_sha256"),
    "geoip_RU_blocked_ip_exact_and_legacy_hard.txt": ("hard.txt", "blocked_exact_and_legacy"),
    "geoip_RU_company_asn_core_bgp_prefixes.txt": ("core.txt", "corporate_core_prefixes"),
    "geoip_RU_shared_infrastructure_bgp_prefixes.txt": ("shared.txt", "shared_infrastructure_prefixes"),
    "kyoresuas-ru-standard-ipv4.txt": ("kyoresuas-v4.txt", "kyoresuas_standard_ipv4"),
    "kyoresuas-ru-standard-ipv6.txt": ("kyoresuas-v6.txt", "kyoresuas_standard_ipv6"),
    "kyoresuas-services.json": ("kyoresuas.json", "kyoresuas_services_json"),
    "w1zardz-ru-ipv4.txt": ("w1zardz.txt", "w1zardz_direct"),
    "hxehex-ipwhitelist.txt": ("hxehex.txt", "hxehex_ipwhitelist"),
    "escapingworm-operator-cidr.txt": ("escapingworm.txt", "escapingworm_operator_whitelist"),
}


def download(name: str) -> bytes:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                RELEASE + name, headers={"User-Agent": "GeoIP-v41-postrelease-audit"}
            )
            with urllib.request.urlopen(req, timeout=90) as response:
                data = response.read()
                if not data:
                    raise ValueError(f"Empty release asset: {name}")
                return data
        except (OSError, ValueError) as exc:
            last = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f"Unable to fetch {name}: {last}")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_and_download(manifest: dict, fetch=download):
    if manifest.get("schema") != 2:
        raise ValueError("Unsupported release manifest")
    sources = manifest.get("input_sha256", {})
    expected = {"geoip_RU.dat": manifest.get("output_sha256")}
    for filename, (_, manifest_field) in INPUTS.items():
        if filename == "geoip_RU.dat":
            continue
        expected[filename] = sources.get(manifest_field)
    if any(not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha)
           for sha in expected.values()):
        raise ValueError("Manifest is missing an input SHA256 required by the audit")

    sidecar_bytes = fetch("geoip_RU_v41_blocked_ip_exclusions.txt.sha256sum")
    sidecar = sidecar_bytes.decode("utf-8").strip()
    match = re.fullmatch(
        r"([0-9a-f]{64})\s+\*?geoip_RU_v41_blocked_ip_exclusions\.txt", sidecar
    )
    if not match:
        raise ValueError("Malformed effective block release checksum sidecar")
    expected["geoip_RU_v41_blocked_ip_exclusions.txt"] = match.group(1)

    verified = {}
    for name, checksum in expected.items():
        payload = fetch(name)
        if digest(payload) != checksum:
            raise ValueError(f"Published release hash differs from manifest/sidecar: {name}")
        verified[name] = payload
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = download("geoip_RU_v41_manifest.json")
    manifest = json.loads(manifest_bytes)
    assets = validate_and_download(manifest)
    mapping = dict(INPUTS)
    mapping["geoip_RU_v41_blocked_ip_exclusions.txt"] = ("effective.txt", None)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for original, payload in assets.items():
        local = mapping[original][0]
        (args.output_dir / local).write_bytes(payload)
    print(json.dumps({
        "status": "VERIFIED",
        "geoip_sha256": manifest["output_sha256"],
        "input_assets_verified": len(assets),
        "generated_at": manifest.get("generated_at"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
