"""Read and verify exact IPv6 assignment conflicts."""
from __future__ import annotations

import csv
import hashlib
import ipaddress
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

RECORD_KEY = "reviewed_ipv6_admission_exclusions"
HEADER = (
    "prefix", "origin_asn", "assignment_country", "basis", "checked_on",
    "rdap_url", "geofeed_url",
)
REGIONAL = {"RU", "BY", "KZ"}


def https_reference(value: str) -> bool:
    if not value.isascii() or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        return False
    url = urlsplit(value)
    return (url.scheme == "https" and bool(url.hostname and url.path)
            and url.username is None and url.password is None and not url.fragment)


def read_reviewed_ipv6_admission(path: Path) -> dict[ipaddress.IPv6Network, dict[str, str]]:
    """Accept exact public IPv6 /48s, never ASN-wide or broader prefix masks.

    The origin records the evidence used in review, not a condition at runtime.
    A later reassignment must be reviewed before changing the exact exclusion.
    """
    rows = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != list(HEADER):
            raise ValueError(f"{path}: invalid reviewed IPv6 admission header")
        for row in reader:
            try:
                if None in row or not all(row.values()):
                    raise ValueError
                prefix, origin, country, basis, checked, rdap, geofeed = (
                    row[key] for key in HEADER
                )
                net = ipaddress.IPv6Network(prefix, strict=True)
                if (str(net) != prefix or net.prefixlen != 48 or not net.is_global
                        or net.is_multicast or net.is_reserved or net.is_site_local
                        or net in rows
                        or not re.fullmatch(r"AS[1-9][0-9]{0,9}", origin)
                        or int(origin[2:]) > 4294967295
                        or not re.fullmatch(r"[A-Z]{2}", country) or country in REGIONAL
                        or basis != "selected_origin_ASN"
                        or date.fromisoformat(checked).isoformat() != checked
                        or rdap != f"https://rdap.db.ripe.net/ip/{prefix}"
                        or not https_reference(geofeed)):
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{reader.line_num}: invalid reviewed IPv6 admission row") from exc
            rows[net] = row
    return rows


def verify_reviewed_ipv6_admission_manifest(path: Path, manifest: dict) -> dict:
    rows = read_reviewed_ipv6_admission(path)
    expected_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if (manifest.get("input_sha256", {}).get(RECORD_KEY) != expected_sha
            or manifest.get(RECORD_KEY, {}).get("records") != list(rows.values())):
        raise ValueError("Reviewed IPv6 admission exclusion provenance mismatch")
    return rows


def main() -> int:
    """Recheck evidence provenance on the downloaded candidate before staging tags."""
    import argparse
    import json

    import build_v41_overlay as builder
    from v41_direct_admission import ROLE, cdn_networks, verify_cdn_manifest

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--geoip", type=Path, required=True)
    parser.add_argument("--hydra", type=Path, required=True)
    parser.add_argument("--regional-table", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        rows = verify_reviewed_ipv6_admission_manifest(args.table, manifest)
        if manifest.get("output_sha256") != hashlib.sha256(args.geoip.read_bytes()).hexdigest():
            raise ValueError("Reviewed IPv6 admission candidate DAT SHA-256 mismatch")
        categories = builder.parse_geoip_dat(args.geoip)
        if set(categories) != {"RU", "PRIVATE"}:
            raise ValueError("Expected GeoIP categories RU and PRIVATE only")
        if manifest.get(RECORD_KEY, {}).get("role") != ROLE:
            raise ValueError("Missing exact foreign admission policy")
        regional = builder.parse_regional_admission_exclusions(args.regional_table)
        if (manifest.get("regional_admission_exclusions", {}).get("role") != ROLE
                or manifest.get("regional_admission_exclusions", {}).get("records") != list(regional.values())
                or manifest.get("input_sha256", {}).get("regional_admission_exclusions")
                != hashlib.sha256(args.regional_table.read_bytes()).hexdigest()):
            raise ValueError("Reviewed IPv4 admission provenance mismatch")
        if manifest.get("input_sha256", {}).get("hydra_geoip") != hashlib.sha256(args.hydra.read_bytes()).hexdigest():
            raise ValueError("Hydra input SHA-256 mismatch")
        hydra = builder.parse_hydra_direct_whitelist(args.hydra)["hydra-direct"]
        cdn = cdn_networks(verify_cdn_manifest(manifest))
        builder.assert_regional_admission_disjoint(
            categories["RU"], builder.subtract_networks(set(rows) | set(regional), hydra, cdn))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print(f"Reviewed foreign admission: verified {len(regional)} IPv4 and {len(rows)} IPv6 exact records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
