#!/usr/bin/env python3
"""Build a prefix-level review queue for company-origin BGP announcements.

This is an audit artifact, not an inclusion policy. The existing DIRECT builder
continues to use its legacy regional/company ASN selection until every proposed
company prefix has explicit prefix-level evidence and a separately reviewed
policy decision.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import ipaddress
import json
import re
import sys
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable

ASN_RE = re.compile(r"AS(?P<asn>[0-9]+)\[(?P<labels>[^\]]*)\]")
COMPANY_HEADER = (
    "ASN", "COMPANY_GROUP", "LEGAL_ENTITY_OR_NOTE", "EVIDENCE",
    "ACTIVE_IN_IPVERSE", "IPVERSE_COUNTRY_CODE", "IPV4_PREFIXES",
    "IPV6_PREFIXES", "ALSO_RIR_RU", "ALSO_RIR_BY_KZ",
)
BGP_HEADER = (
    "PREFIX", "FAMILY", "ADDRESS_COUNT", "COMPANY_ASNS", "COMPANY_GROUPS",
    "LEGAL_ENTITIES", "ASN_EVIDENCE_URLS", "COMPANY_ASN_DETAILS_JSON",
    "SELECTED_ORIGIN_ASNS", "SELECTED_ORIGIN_LABELS", "REGIONAL_RIR_ASNS",
    "REGIONAL_RIR_ASN_ORIGIN", "INCLUSION_BASIS", "GLOBAL_BGP_ORIGIN_ASNS",
    "GLOBAL_BGP_ORIGIN_COUNTRY_CODES", "GLOBAL_BGP_MOAS", "RPKI_STATUS",
    "IRR_STATUS", "STATUS", "CURRENT_PIPELINE_EVIDENCE", "REVIEW_REASON",
    "GENERATED_UTC", "BGP_SNAPSHOT_SHA256", "BGP_SNAPSHOT_URL",
)
REVIEW_REASON = (
    "ASN-level affiliation is only a candidate selector; it does not prove that "
    "this exact prefix is allocated to or controlled by the company, nor that "
    "it should be DIRECT. Verify prefix-level RIR/RDAP ownership, RPKI/ROA, "
    "IRR, company evidence, and hosting/customer/CDN role."
)


def _read_tsv(path: Path) -> list[list[str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.reader(handle, delimiter="\t"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def read_company_registry(path: Path) -> dict[int, dict[str, str]]:
    rows = _read_tsv(path)
    companies: dict[int, dict[str, str]] = {}
    for line_no, row in enumerate(rows, 1):
        if not row or not any(cell.strip() for cell in row):
            continue
        if row[0].lstrip().startswith("#"):
            continue
        if len(row) != 4:
            raise ValueError(f"{path}:{line_no}: expected four tab-separated fields")
        match = re.fullmatch(r"AS([0-9]+)", row[0].strip(), re.IGNORECASE)
        if not match:
            raise ValueError(f"{path}:{line_no}: invalid ASN {row[0]!r}")
        asn = int(match.group(1))
        group, entity, evidence = (cell.strip() for cell in row[1:])
        if not group or not entity or not evidence:
            raise ValueError(f"{path}:{line_no}: company group, entity and evidence are required")
        if asn in companies:
            raise ValueError(f"{path}:{line_no}: duplicate company ASN AS{asn}")
        companies[asn] = {
            "group": group,
            "entity": entity,
            "evidence": evidence,
        }
    if not companies:
        raise ValueError(f"{path}: company ASN registry is empty")
    return companies


def read_company_manifest(path: Path, companies: dict[int, dict[str, str]]) -> dict[int, dict[str, str]]:
    rows = _read_tsv(path)
    expected = list(COMPANY_HEADER)
    if not rows or tuple(rows[0]) != tuple(expected):
        raise ValueError(f"{path}: unexpected company ASN manifest schema")
    countries: dict[int, dict[str, str]] = {}
    for line_no, row in enumerate(rows[1:], 2):
        if not row:
            continue
        if len(row) != len(COMPANY_HEADER):
            raise ValueError(f"{path}:{line_no}: malformed company ASN manifest row")
        match = re.fullmatch(r"AS([0-9]+)", row[0].strip(), re.IGNORECASE)
        if not match:
            raise ValueError(f"{path}:{line_no}: invalid ASN {row[0]!r}")
        asn = int(match.group(1))
        if asn in countries:
            raise ValueError(f"{path}:{line_no}: duplicate company ASN AS{asn}")
        rir_ru = row[8].strip().lower()
        rir_by_kz = row[9].strip().lower()
        if rir_ru not in {"yes", "no"} or rir_by_kz not in {"yes", "no"}:
            raise ValueError(f"{path}:{line_no}: invalid RIR registration flags for AS{asn}")
        countries[asn] = {
            "ipverse_country_code": row[5].strip().upper() or "UNKNOWN",
            "also_rir_ru": rir_ru,
            "also_rir_by_kz": rir_by_kz,
        }
    missing = sorted(set(companies) - set(countries))
    if missing:
        raise ValueError("company ASN manifest is missing registry entries: " +
                         ", ".join(f"AS{asn}" for asn in missing))
    extra = sorted(set(countries) - set(companies))
    if extra:
        raise ValueError("company ASN manifest contains ASN entries absent from registry: " +
                         ", ".join(f"AS{asn}" for asn in extra))
    return countries


def read_bgp_snapshot(path: Path, archive_path: Path) -> tuple[str, str]:
    rows = _read_tsv(path)
    expected = ["SOURCE", "LOCAL_FILE", "FETCH_URL", "SHA256", "BYTES", "STATUS"]
    if not rows or rows[0] != expected:
        raise ValueError(f"{path}: unexpected input provenance schema")
    matches = [row for row in rows[1:] if len(row) == 6 and row[1] == "as-ip-blocks.tar.gz"]
    if len(matches) != 1:
        raise ValueError("input provenance must contain exactly one as-ip-blocks.tar.gz row")
    row = matches[0]
    if row[5] != "downloaded" or not re.fullmatch(r"[0-9a-f]{64}", row[3]):
        raise ValueError("BGP snapshot is not marked downloaded with a valid SHA-256")
    if not row[2].startswith("https://"):
        raise ValueError("BGP snapshot URL must use HTTPS")
    if not row[4].isdigit():
        raise ValueError("BGP snapshot provenance BYTES field must be a positive integer")
    try:
        archive_bytes = archive_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read BGP snapshot {archive_path}: {exc}") from exc
    actual_size = len(archive_bytes)
    if actual_size != int(row[4]):
        raise ValueError(
            f"BGP snapshot size mismatch: manifest={row[4]} actual={actual_size}"
        )
    actual_sha = hashlib.sha256(archive_bytes).hexdigest()
    if actual_sha != row[3]:
        raise ValueError(
            f"BGP snapshot SHA-256 mismatch: manifest={row[3]} actual={actual_sha}"
        )
    return row[3], row[2]


def read_global_bgp_origins(
    archive_path: Path,
    target_prefixes: set[str],
) -> tuple[dict[str, set[int]], dict[str, dict[int, str]]]:
    """Return every origin ASN observed for target prefixes in the same ipverse snapshot."""
    origins: dict[str, set[int]] = defaultdict(set)
    countries: dict[str, dict[int, str]] = defaultdict(dict)
    json_files = 0
    malformed_json = 0

    try:
        archive = tarfile.open(archive_path, mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise ValueError(f"invalid ipverse BGP archive {archive_path}: {exc}") from exc

    with archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith("aggregated.json"):
                continue
            stream = archive.extractfile(member)
            if stream is None:
                malformed_json += 1
                continue
            try:
                item = json.load(stream)
            except (json.JSONDecodeError, UnicodeDecodeError):
                malformed_json += 1
                continue
            json_files += 1

            try:
                asn = int(item.get("asn"))
            except (AttributeError, TypeError, ValueError):
                continue
            metadata = item.get("metadata") or {}
            country_code = str(metadata.get("countryCode") or "UNKNOWN").upper()
            prefixes = item.get("prefixes") or {}
            for family, version in (("ipv4", 4), ("ipv6", 6)):
                for raw_prefix in prefixes.get(family, []) or []:
                    try:
                        network = ipaddress.ip_network(str(raw_prefix), strict=False)
                    except ValueError:
                        continue
                    if network.version != version or network.prefixlen == 0:
                        continue
                    normalized = network.with_prefixlen
                    if normalized in target_prefixes:
                        origins[normalized].add(asn)
                        countries[normalized][asn] = country_code

    if malformed_json:
        raise ValueError(
            f"ipverse archive contains {malformed_json} malformed aggregated.json files"
        )
    if json_files == 0:
        raise ValueError("ipverse archive contains no aggregated.json files")

    missing = sorted(target_prefixes - set(origins))
    if missing:
        examples = ", ".join(missing[:10])
        raise ValueError(
            f"{len(missing)} company-origin prefixes from selected input are absent "
            f"from the global BGP snapshot; examples: {examples}"
        )
    return dict(origins), dict(countries)


def _prefix_sort_key(prefix: str) -> tuple[int, int, int]:
    net = ipaddress.ip_network(prefix, strict=True)
    return net.version, int(net.network_address), net.prefixlen


def _union_addresses(prefixes: Iterable[str], version: int) -> int:
    nets = [ipaddress.ip_network(value, strict=True)
            for value in set(prefixes)
            if ipaddress.ip_network(value, strict=True).version == version]
    if not nets:
        return 0
    return sum(net.num_addresses for net in ipaddress.collapse_addresses(nets))


def build_review(
    company_registry: Path,
    company_manifest: Path,
    regional_prefixes: Path,
    input_provenance: Path,
    bgp_archive: Path,
    output: Path,
    stats: Path,
) -> tuple[int, int, int]:
    companies = read_company_registry(company_registry)
    countries = read_company_manifest(company_manifest, companies)
    snapshot_sha, snapshot_url = read_bgp_snapshot(input_provenance, bgp_archive)
    generated = dt.datetime.now(dt.timezone.utc).isoformat()

    records: dict[str, dict[str, object]] = {}
    try:
        source_lines = regional_prefixes.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read selected BGP prefixes {regional_prefixes}: {exc}") from exc

    for line_no, raw in enumerate(source_lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        prefix_token, separator, comment = line.partition("#")
        if not separator:
            raise ValueError(f"{regional_prefixes}:{line_no}: missing origin annotation")
        try:
            network = ipaddress.ip_network(prefix_token.strip(), strict=True)
        except ValueError as exc:
            raise ValueError(f"{regional_prefixes}:{line_no}: invalid prefix {prefix_token.strip()!r}") from exc

        origins: list[tuple[int, set[str]]] = []
        for match in ASN_RE.finditer(comment):
            asn = int(match.group("asn"))
            labels = {part.strip() for part in match.group("labels").split("+") if part.strip()}
            origins.append((asn, labels))
        if not origins:
            continue

        company_origins = [(asn, labels) for asn, labels in origins if asn in companies]
        if not company_origins:
            continue

        key = network.with_prefixlen
        item = records.setdefault(key, {
            "network": network,
            "company_asns": set(),
            "company_groups": set(),
            "entities": set(),
            "evidence": set(),
            "countries": set(),
            "selected_origins": set(),
            "selected_origin_labels": defaultdict(set),
            "regional_origins": set(),
        })
        item["selected_origins"].update(asn for asn, _ in origins)
        for asn, labels in origins:
            item["selected_origin_labels"][asn].update(labels)
        item["company_asns"].update(asn for asn, _ in company_origins)
        for asn, labels in company_origins:
            company = companies[asn]
            item["company_groups"].add(company["group"])
            item["entities"].add(company["entity"])
            item["evidence"].add(company["evidence"])
            item["countries"].add(countries[asn]["ipverse_country_code"])
        for asn, labels in origins:
            if "RIR-RU" in labels or "RIR-BY/KZ" in labels:
                item["regional_origins"].add(asn)

    if not records:
        raise ValueError("no company-origin prefixes were found in the selected BGP manifest")

    global_origins, global_countries = read_global_bgp_origins(
        bgp_archive, set(records)
    )

    def join_values(values: Iterable[object]) -> str:
        return ",".join(str(value) for value in sorted(values, key=lambda value: str(value)))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"# Generated UTC: {generated}\n")
        handle.write(f"# BGP source URL: {snapshot_url}\n")
        handle.write(f"# BGP source SHA256: {snapshot_sha}\n")
        handle.write("# RPKI and IRR were not queried by this report; NOT_QUERIED is not a negative result.\n")
        handle.write("# Every row is REVIEW; this file does not approve or reject a prefix and does not alter the current GeoIP output.\n")
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(BGP_HEADER)
        for prefix in sorted(records, key=_prefix_sort_key):
            item = records[prefix]
            net = item["network"]
            regional_asns = item["regional_origins"]
            regional = bool(regional_asns)
            basis = "COMPANY_ASN_ONLY"
            if regional:
                basis = "REGIONAL_RIR_ASN_ORIGIN+COMPANY_ASN"
            company_details = [
                {
                    "asn": f"AS{asn}",
                    "group": companies[asn]["group"],
                    "legal_entity": companies[asn]["entity"],
                    "ipverse_country_code": countries[asn]["ipverse_country_code"],
                    "also_rir_ru": countries[asn]["also_rir_ru"],
                    "also_rir_by_kz": countries[asn]["also_rir_by_kz"],
                    "evidence_url": companies[asn]["evidence"],
                }
                for asn in sorted(item["company_asns"])
            ]
            global_origin_asns = global_origins[prefix]
            global_origin_countries = global_countries[prefix]
            selected_labels = [
                f"AS{asn}[{'+'.join(sorted(item['selected_origin_labels'][asn]))}]"
                for asn in sorted(item["selected_origins"])
            ]
            writer.writerow([
                prefix,
                f"IPv{net.version}",
                net.num_addresses,
                join_values(f"AS{asn}" for asn in item["company_asns"]),
                join_values(item["company_groups"]),
                join_values(item["entities"]),
                join_values(item["evidence"]),
                json.dumps(company_details, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                join_values(f"AS{asn}" for asn in item["selected_origins"]),
                ",".join(selected_labels),
                join_values(f"AS{asn}" for asn in regional_asns),
                "yes" if regional else "no",
                basis,
                join_values(f"AS{asn}" for asn in global_origin_asns),
                join_values(f"AS{asn}={global_origin_countries[asn]}" for asn in global_origin_asns),
                "yes" if len(global_origin_asns) > 1 else "no",
                "NOT_QUERIED",
                "NOT_QUERIED",
                "REVIEW",
                "PRESENT_IN_SELECTED_BGP_INPUT",
                REVIEW_REASON,
                generated,
                snapshot_sha,
                snapshot_url,
            ])

    all_prefixes = set(records)
    company_only = {
        prefix for prefix, item in records.items()
        if not item["regional_origins"]
    }
    regional_and_company = all_prefixes - company_only
    v4_all = _union_addresses(all_prefixes, 4)
    v6_all = _union_addresses(all_prefixes, 6)
    v4_only = _union_addresses(company_only, 4)
    v6_only = _union_addresses(company_only, 6)
    v4_regional = _union_addresses(regional_and_company, 4)
    v6_regional = _union_addresses(regional_and_company, 6)

    moas_count = sum(1 for prefix in all_prefixes if len(global_origins[prefix]) > 1)
    stats_lines = [
        f"Generated UTC: {generated}",
        f"BGP snapshot URL: {snapshot_url}",
        f"BGP snapshot SHA256: {snapshot_sha}",
        f"Company ASN registry entries: {len(companies)}",
        f"Unique prefixes with at least one company origin ASN: {len(all_prefixes)}",
        f"Prefixes with multiple global BGP origin ASNs (MOAS): {moas_count}",
        f"Unique IPv4 company-origin prefixes: {sum(1 for p in all_prefixes if ipaddress.ip_network(p).version == 4)}",
        f"Unique IPv6 company-origin prefixes: {sum(1 for p in all_prefixes if ipaddress.ip_network(p).version == 6)}",
        f"Company-origin IPv4 address-space union: {v4_all}",
        f"Company-origin IPv6 address-space union: {v6_all}",
        f"Prefixes also originated by selected RIR-RU/BY/KZ ASNs: {len(regional_and_company)}",
        f"Prefixes without selected RIR-RU/BY/KZ ASN origin: {len(company_only)}",
        f"Company-only IPv4 address-space union (independent; may overlap other classes): {v4_only}",
        f"Company-only IPv6 address-space union (independent; may overlap other classes): {v6_only}",
        f"Company+regional-origin IPv4 address-space union (independent): {v4_regional}",
        f"Company+regional-origin IPv6 address-space union (independent): {v6_regional}",
        "Prefix review status: REVIEW for every row; no per-prefix ownership/control decision is inferred from ASN membership.",
        "Global origin ASNs are derived from every aggregated.json record in the same ipverse snapshot, not only ASNs selected for DIRECT.",
        "The ipverse observation window is up to 90 days; observed origin ASNs do not prove ownership or a complete live BGP RIB.",
        "RPKI/ROA status: NOT_QUERIED; this is not a statement that a route is invalid or lacks a ROA.",
        "IRR status: NOT_QUERIED; this is not a statement that a route object is absent.",
        "Current build behavior: prefixes remain present in the selected BGP input under the legacy ASN-selection rule; this report does not change routing or the protobuf.",
        "Address-space totals are calculated as unions after CIDR collapse; do not add independent class totals.",
    ]
    stats.write_text("\n".join(stats_lines) + "\n", encoding="utf-8")
    print("\n".join(stats_lines))
    return len(all_prefixes), len(company_only), len(regional_and_company)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-asns", type=Path, required=True)
    parser.add_argument("--company-manifest", type=Path, required=True)
    parser.add_argument("--regional-prefixes", type=Path, required=True)
    parser.add_argument("--input-provenance", type=Path, required=True)
    parser.add_argument("--bgp-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_review(
            args.company_asns,
            args.company_manifest,
            args.regional_prefixes,
            args.input_provenance,
            args.bgp_archive,
            args.output,
            args.stats,
        )
    except (OSError, ValueError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
