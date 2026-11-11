#!/usr/bin/env python3
"""Validate the versioned, metadata-only production GeoIP source catalog."""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "docs" / "GEOIP_RU_SOURCE_CATALOG_v1.tsv"
REQUIRED_COLUMNS = (
    "SOURCE_ID", "SOURCE_LAYER", "LOCAL_INPUT", "FORMAT", "UPSTREAM_PRIMARY",
    "UPSTREAM_FALLBACKS", "ACQUISITION", "REQUIREDNESS", "PRODUCTION_ROLE",
    "IMPORT_OR_SELECTION_RULE", "REF_PINNING", "PROVENANCE_CAPTURE",
    "LICENSE_STATUS", "LIMITATIONS",
)
REQUIRED_SOURCE_IDS = {
    "geoip-loyalsoldier-ru", "geoip-loyalsoldier-by", "geoip-loyalsoldier-private",
    "geoip-v2fly-db", "geoip-v2fly-sha256", "geoip-grimbird", "geoip-digne",
    "geoip-davoyan", "geoip-golukon", "geoip-hydra", "geoip-kirill",
    "candidate-hxehex", "candidate-w1zardz",
    "rir-afrinic", "rir-apnic", "rir-arin", "rir-lacnic", "rir-ripencc",
    "iana-ipv4-special", "iana-ipv6-special", "bgp-ipverse",
    "policy-company-asn-allowlist", "blocked-antifilter-ip",
    "blocked-antifilter-ipresolve", "blocked-antifilter-subnet",
    "review-antifilter-community", "review-refilter-ipsum",
    "policy-runetfreedom-telegram", "policy-builtin-private",
}
ALLOWED_REQUIREDNESS = {"required", "optional", "embedded", "derived"}
SOURCE_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class CatalogError(ValueError):
    """The source catalog is malformed or incomplete."""


def _https_url(value: str, field: str, source_id: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CatalogError(f"{source_id}: {field} contains a non-HTTPS or malformed URL: {value!r}")


def load_catalog(path: Path = DEFAULT_CATALOG) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(
                (line for line in stream if not line.startswith("#")), delimiter="\t"
            )
            if reader.fieldnames is None:
                raise CatalogError(f"catalog has no header: {path}")
            missing = sorted(set(REQUIRED_COLUMNS) - set(reader.fieldnames))
            if missing:
                raise CatalogError(f"catalog is missing columns: {missing}")
            rows = list(reader)
    except OSError as exc:
        raise CatalogError(f"cannot read catalog {path}: {exc}") from exc
    if not rows:
        raise CatalogError("catalog has no data rows")
    return rows


def validate_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, object]:
    rows = load_catalog(path)
    by_id: dict[str, dict[str, str]] = {}
    layers: Counter[str] = Counter()
    for line_no, row in enumerate(rows, 2):
        source_id = row.get("SOURCE_ID", "").strip()
        if not SOURCE_ID_RE.fullmatch(source_id):
            raise CatalogError(f"line {line_no}: invalid SOURCE_ID {source_id!r}")
        if source_id in by_id:
            raise CatalogError(f"duplicate SOURCE_ID: {source_id}")
        by_id[source_id] = row
        layers[row.get("SOURCE_LAYER", "")] += 1

        nonblank_fields = (
            "SOURCE_ID", "SOURCE_LAYER", "LOCAL_INPUT", "FORMAT", "ACQUISITION",
            "REQUIREDNESS", "PRODUCTION_ROLE", "IMPORT_OR_SELECTION_RULE",
            "REF_PINNING", "PROVENANCE_CAPTURE", "LICENSE_STATUS", "LIMITATIONS",
        )
        missing_values = [
            field for field in nonblank_fields
            if field not in row or not row[field].strip()
        ]
        if missing_values:
            raise CatalogError(f"{source_id}: blank required fields: {missing_values}")

        requiredness = row["REQUIREDNESS"].strip()
        if requiredness not in ALLOWED_REQUIREDNESS:
            raise CatalogError(f"{source_id}: invalid REQUIREDNESS {requiredness!r}")

        primary = row["UPSTREAM_PRIMARY"].strip()
        if requiredness in {"required", "optional"} and not primary:
            raise CatalogError(f"{source_id}: downloaded source has no UPSTREAM_PRIMARY")
        if primary:
            _https_url(primary, "UPSTREAM_PRIMARY", source_id)

        fallbacks = [
            value.strip() for value in row["UPSTREAM_FALLBACKS"].split("|")
            if value.strip()
        ]
        for fallback in fallbacks:
            _https_url(fallback, "UPSTREAM_FALLBACKS", source_id)

        if requiredness == "derived" and (primary or fallbacks):
            raise CatalogError(f"{source_id}: derived rows must reference parents, not direct download URLs")
        if requiredness == "embedded" and not row["ACQUISITION"].strip().startswith((
            "embedded policy", "not downloaded; static", "local file / embedded fallback"
        )):
            raise CatalogError(f"{source_id}: unexpected embedded acquisition mode")

    missing_ids = sorted(REQUIRED_SOURCE_IDS - set(by_id))
    if missing_ids:
        raise CatalogError(f"catalog is missing required production source IDs: {missing_ids}")

    if len(rows) != 38:
        raise CatalogError(f"catalog row count changed: expected 38, got {len(rows)}")

    # Guard the semantic boundaries that are easiest to accidentally blur.
    role_expectations = {
        "geoip-hydra": "CANDIDATE_ONLY",
        "geoip-kirill": "CANDIDATE_ONLY",
        "candidate-hxehex": "CANDIDATE_ONLY",
        "candidate-w1zardz": "CANDIDATE_ONLY",
        "geoip-digne": "ADDITIONAL_RU_FEED_CORRELATED",
        "geoip-grimbird": "ADDITIONAL_RU_FEED_CORRELATED",
        "policy-runetfreedom-telegram": "CURATED_AUTO_BLOCKED_EXCEPTION",
        "review-antifilter-community": "REVIEW_ONLY_NO_CARVE",
        "review-refilter-ipsum": "REVIEW_ONLY_NO_CARVE",
        "derived-rir-ru-prefixes": "CORROBORATION_ONLY",
        "derived-global-bgp": "GLOBAL_ROUTING_OBSERVATION_ONLY",
    }
    for source_id, expected_role in role_expectations.items():
        actual = by_id[source_id]["PRODUCTION_ROLE"].strip()
        if actual != expected_role:
            raise CatalogError(
                f"{source_id}: production role drifted; expected {expected_role}, got {actual}"
            )

    return {
        "rows": len(rows),
        "unique_source_ids": len(by_id),
        "layers": dict(sorted(layers.items())),
        "required_ids": len(REQUIRED_SOURCE_IDS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args()
    try:
        result = validate_catalog(args.catalog)
    except CatalogError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        f"Validated {result['rows']} GeoIP source catalog rows "
        f"({result['unique_source_ids']} unique IDs); layers={result['layers']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
