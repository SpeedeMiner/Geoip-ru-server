#!/usr/bin/env python3
"""Validate and map a voluntarily supplied local home-probe report.

This is a local-only review tool. It never uploads results or changes GeoIP data.
A report is accepted for RU source-network review only when two independent
metadata services agree on the same globally routable egress IP and RU country.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import pathlib
import sys
from typing import Any

import runner

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_TARGETS = SCRIPT_DIR / "targets.json"

PROVIDER_FIELDS = [
    "OBSERVED_AT", "SOURCE_PUBLIC_IP", "SOURCE_COUNTRY",
    "SOURCE_ASN_CANDIDATES", "SOURCE_ORGANIZATIONS",
    "SOURCE_ATTRIBUTION_STATUS", "SOURCE_METADATA_PROVIDERS",
    "GEOIP_CATEGORY", "MATCHED_GEOIP_PREFIX",
    "ACCESS_NETWORK_CLASS", "RESIDENTIAL_ATTESTATION",
]
OBSERVATION_FIELDS = [
    "OBSERVED_AT", "TARGET_ID", "TARGET_DOMAIN", "TARGET_ROLE",
    "FAMILY", "DNS_STATUS", "DNS_ADDRESS", "GEOIP_CATEGORY",
    "MATCHED_GEOIP_PREFIX", "HTTPS_TESTED_ADDRESS",
    "HTTPS_RESULT", "HTTP_STATUS", "ERROR",
]
CANDIDATE_FIELDS = [
    "CANDIDATE_TYPE", "SOURCE_PUBLIC_IP", "SOURCE_COUNTRY",
    "SOURCE_ASN_CANDIDATES", "SOURCE_ORGANIZATIONS",
    "GEOIP_CATEGORY", "MATCHED_RU_PREFIX", "REASON", "REVIEW_POLICY",
]


class ImportError(RuntimeError):
    pass


def read_object(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportError(f"cannot read valid JSON from {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ImportError(f"{path.name} must contain a JSON object")
    return value


def read_measurements(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ImportError(
                        f"{path.name}:{line_number}: invalid JSON: {exc}"
                    ) from exc
                if not isinstance(row, dict):
                    raise ImportError(f"{path.name}:{line_number}: expected JSON object")
                rows.append(row)
    except OSError as exc:
        raise ImportError(f"cannot read {path.name}: {exc}") from exc
    return rows


def validate_source(
    source: dict[str, Any], summary: dict[str, Any], required_country: str
) -> str:
    observations = source.get("observations")
    if not isinstance(observations, list):
        raise ImportError("source metadata has no observations list")
    providers = {
        str(item.get("provider") or "").strip().lower()
        for item in observations if isinstance(item, dict)
    }
    providers.discard("")
    if len(providers) < 2:
        raise ImportError("source report does not contain two distinct metadata providers")
    if source.get("verified") is not True or source.get("status") != "TWO_SOURCE_CONSENSUS":
        raise ImportError("source public IP/country is not verified by two metadata services")
    if summary.get("source_ip_verified_by_two_services") is not True:
        raise ImportError("summary does not confirm two-source source-IP verification")
    if summary.get("automatic_upload") is not False or summary.get("geoip_mutation") is not False:
        raise ImportError("report does not carry the expected local-only/review-only policy")
    if summary.get("proxy_environment_variables") not in ([], None):
        raise ImportError("report indicates proxy environment variables were present")
    if source.get("required_country") != required_country:
        raise ImportError("source report was collected for a different required country")
    if source.get("required_country_matches") is not True:
        raise ImportError("source country does not match the requested country")
    if source.get("country") != required_country or summary.get("source_country") != required_country:
        raise ImportError(f"verified source country is not {required_country}")

    address = str(source.get("public_ip") or "").strip()
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ImportError("verified source public IP is invalid") from exc
    if not parsed.is_global or str(parsed) != address:
        raise ImportError("verified source public IP is not canonical/global")
    if summary.get("source_public_ip") != address:
        raise ImportError("source public IP differs between source and summary reports")

    for item in observations:
        if not isinstance(item, dict):
            raise ImportError("source metadata observation is not an object")
        try:
            item_ip = str(ipaddress.ip_address(str(item.get("ip") or "")))
        except ValueError as exc:
            raise ImportError("source metadata provider has an invalid IP") from exc
        if item_ip != address or item.get("country") != required_country:
            raise ImportError("source metadata provider observations do not agree")
    return address


def validate_family(
    row: dict[str, Any],
    family: str,
) -> tuple[str, list[str], str, str, int | None, str]:
    key = "ipv4" if family == "IPv4" else "ipv6"
    status = row.get(f"dns_{key}_status")
    addresses = row.get(f"dns_{key}_addresses")
    error = str(row.get(f"dns_{key}_error") or "")
    tested_address = str(row.get(f"https_{key}_tested_address") or "")
    https_result = row.get(f"https_{key}_result")
    http_status = row.get(f"https_{key}_status")
    https_error = str(row.get(f"https_{key}_error") or "")

    if status not in {"DNS_ANSWER", "DNS_NO_ANSWER", "DNS_ERROR"}:
        raise ImportError(f"invalid {family} DNS status for target {row.get('target_id')}")
    if not isinstance(addresses, list):
        raise ImportError(f"{family} DNS addresses must be a list")
    normalized: list[str] = []
    for value in addresses:
        try:
            parsed = ipaddress.ip_address(str(value))
        except ValueError as exc:
            raise ImportError(f"invalid {family} DNS address for target {row.get('target_id')}") from exc
        expected_version = 4 if family == "IPv4" else 6
        if parsed.version != expected_version or not parsed.is_global:
            raise ImportError(f"non-global or wrong-family {family} DNS address in report")
        canonical = str(parsed)
        if canonical in normalized:
            raise ImportError(f"duplicate {family} DNS address in report")
        normalized.append(canonical)

    if status == "DNS_ANSWER" and not normalized:
        raise ImportError(f"{family} DNS_ANSWER has no addresses")
    if status != "DNS_ANSWER" and normalized:
        raise ImportError(f"{family} DNS status {status} unexpectedly has addresses")

    if https_result not in {"HTTP_RESPONSE", "INCONCLUSIVE", "NOT_TESTED"}:
        raise ImportError(f"invalid {family} HTTPS result for target {row.get('target_id')}")
    if https_result == "NOT_TESTED":
        if tested_address or http_status is not None:
            raise ImportError(f"{family} NOT_TESTED result has an address/status")
    else:
        if not normalized or tested_address != normalized[0]:
            raise ImportError(f"{family} HTTPS-tested address is not the first observed DNS address")
    if https_result == "HTTP_RESPONSE":
        if not isinstance(http_status, int) or not 100 <= http_status <= 599:
            raise ImportError(f"{family} HTTP_RESPONSE has an invalid HTTP status")
    elif http_status is not None:
        raise ImportError(f"{family} non-response has an unexpected HTTP status")
    return status, normalized, error, tested_address, http_status, f"{https_result}: {https_error}"


def validate_report(
    report_dir: pathlib.Path,
    targets_path: pathlib.Path,
    required_country: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    source = read_object(report_dir / "home_probe_source.json")
    summary = read_object(report_dir / "home_probe_summary.json")
    measurements = read_measurements(report_dir / "home_probe_measurements.jsonl")
    source_ip = validate_source(source, summary, required_country)
    if summary.get("probe_type") != "USER_CONTROLLED_HOME_OR_ACCESS_NETWORK":
        raise ImportError("unexpected probe_type in summary")
    if summary.get("required_country") != required_country:
        raise ImportError("summary country does not match requested import country")
    if summary.get("target_count") != len(measurements) or not measurements:
        raise ImportError("measurement count does not match summary or is empty")

    targets = runner.load_targets(targets_path)
    expected = {target["id"]: target for target in targets}
    seen: set[str] = set()
    for row in measurements:
        target_id = str(row.get("target_id") or "")
        target = expected.get(target_id)
        if target is None:
            raise ImportError(f"unknown target ID in report: {target_id!r}")
        if target_id in seen:
            raise ImportError(f"duplicate target measurement: {target_id}")
        seen.add(target_id)
        if row.get("source") != "user_controlled_home_probe":
            raise ImportError(f"unexpected measurement source for target {target_id}")
        if row.get("target_domain") != target["domain"] or row.get("target_role") != target["role"]:
            raise ImportError(f"target metadata does not match current catalogue: {target_id}")
        if required_country not in target.get("country_scope", []):
            raise ImportError(f"target {target_id} is not scoped for {required_country}")
        if not str(row.get("observed_at") or "").strip():
            raise ImportError(f"missing observation timestamp for target {target_id}")
        validate_family(row, "IPv4")
        validate_family(row, "IPv6")
    return source, summary, measurements, {"source_ip": source_ip, "targets": expected}


def ingest_report(args: argparse.Namespace) -> dict[str, Any]:
    report_dir = pathlib.Path(args.report_dir)
    if not report_dir.is_dir():
        raise ImportError(f"report directory does not exist: {report_dir}")
    source, summary, measurements, details = validate_report(
        report_dir, pathlib.Path(args.targets), args.required_country
    )
    inventory_rows, networks = runner.read_inventory(pathlib.Path(args.inventory))
    source_ip = details["source_ip"]
    source_category, source_prefix = runner.map_address(source_ip, networks)
    source_asns = "|".join(str(value) for value in source.get("asn_candidates", []))
    source_orgs = "|".join(str(value) for value in source.get("organizations", []))
    metadata_providers = "|".join(sorted({
        str(item.get("provider") or "") for item in source.get("observations", [])
    }))
    provider_row = {
        "OBSERVED_AT": summary.get("generated_at", ""),
        "SOURCE_PUBLIC_IP": source_ip,
        "SOURCE_COUNTRY": source.get("country", ""),
        "SOURCE_ASN_CANDIDATES": source_asns,
        "SOURCE_ORGANIZATIONS": source_orgs,
        "SOURCE_ATTRIBUTION_STATUS": source.get("status", ""),
        "SOURCE_METADATA_PROVIDERS": metadata_providers,
        "GEOIP_CATEGORY": source_category,
        "MATCHED_GEOIP_PREFIX": source_prefix,
        "ACCESS_NETWORK_CLASS": "RESIDENTIAL_OR_OTHER_ACCESS_NETWORK_UNVERIFIED",
        "RESIDENTIAL_ATTESTATION": "NOT_VERIFIED",
    }

    observations: list[dict[str, Any]] = []
    for row in measurements:
        for family in ("IPv4", "IPv6"):
            key = "ipv4" if family == "IPv4" else "ipv6"
            dns_status, addresses, dns_error, tested_address, http_status, https_detail = validate_family(row, family)
            https_result = https_detail.split(":", 1)[0]
            if not addresses:
                observations.append({
                    "OBSERVED_AT": row["observed_at"],
                    "TARGET_ID": row["target_id"],
                    "TARGET_DOMAIN": row["target_domain"],
                    "TARGET_ROLE": row["target_role"],
                    "FAMILY": family,
                    "DNS_STATUS": dns_status,
                    "DNS_ADDRESS": "",
                    "GEOIP_CATEGORY": "NO_RESOLVED_ADDRESS",
                    "MATCHED_GEOIP_PREFIX": "",
                    "HTTPS_TESTED_ADDRESS": "",
                    "HTTPS_RESULT": https_result,
                    "HTTP_STATUS": "",
                    "ERROR": " | ".join(value for value in (dns_error, https_detail.split(": ",1)[-1] if https_detail.startswith("INCONCLUSIVE:") else "") if value)[:500],
                })
                continue
            for address in addresses:
                category, prefix = runner.map_address(address, networks)
                is_tested = address == tested_address
                observations.append({
                    "OBSERVED_AT": row["observed_at"],
                    "TARGET_ID": row["target_id"],
                    "TARGET_DOMAIN": row["target_domain"],
                    "TARGET_ROLE": row["target_role"],
                    "FAMILY": family,
                    "DNS_STATUS": dns_status,
                    "DNS_ADDRESS": address,
                    "GEOIP_CATEGORY": category,
                    "MATCHED_GEOIP_PREFIX": prefix,
                    "HTTPS_TESTED_ADDRESS": tested_address if is_tested else "",
                    "HTTPS_RESULT": https_result if is_tested else "NOT_TESTED_ALTERNATE_ADDRESS",
                    "HTTP_STATUS": http_status if is_tested and http_status is not None else "",
                    "ERROR": " | ".join(value for value in (dns_error, https_detail.split(": ",1)[-1] if is_tested and https_detail.startswith("INCONCLUSIVE:") else "") if value)[:500],
                })

    candidates: list[dict[str, Any]] = []
    if source_category == "OUTSIDE_GEOIP_RU":
        candidates.append({
            "CANDIDATE_TYPE": "HOME_PROBE_SOURCE_IP",
            "SOURCE_PUBLIC_IP": source_ip,
            "SOURCE_COUNTRY": source.get("country", ""),
            "SOURCE_ASN_CANDIDATES": source_asns,
            "SOURCE_ORGANIZATIONS": source_orgs,
            "GEOIP_CATEGORY": source_category,
            "MATCHED_RU_PREFIX": "",
            "REASON": "Two metadata services agree the user-controlled probe's public egress IP is in the required country, but it is outside the published RU inventory.",
            "REVIEW_POLICY": "EXACT_IP_ONLY_VERIFY_ORIGIN_ASN_AND_ACCESS_TYPE_NO_AUTOMATIC_CIDR_ADDITION",
        })

    output = pathlib.Path(args.output_dir)
    if output.exists() and any(output.iterdir()):
        raise ImportError(f"output directory is not empty: {output}; choose a fresh directory")
    output.mkdir(parents=True, exist_ok=True)
    runner.write_tsv(output / "home_probe_provider.tsv", [provider_row], PROVIDER_FIELDS)
    runner.write_tsv(output / "home_probe_observations.tsv", observations, OBSERVATION_FIELDS)
    runner.write_tsv(output / "home_probe_candidates.tsv", candidates, CANDIDATE_FIELDS)

    dns_addresses = [item for item in observations if item["DNS_ADDRESS"]]
    result = {
        "generated_at": utc_now(),
        "input_report_dir": str(report_dir),
        "required_country": args.required_country,
        "source_public_ip": source_ip,
        "source_geoip_category": source_category,
        "source_matched_ru_prefix": source_prefix,
        "source_candidate_count": len(candidates),
        "dns_observation_rows": len(observations),
        "dns_addresses_observed": len(dns_addresses),
        "dns_addresses_in_ru_inventory": sum(item["GEOIP_CATEGORY"] == "RU" for item in dns_addresses),
        "dns_addresses_private": sum(item["GEOIP_CATEGORY"] == "PRIVATE" for item in dns_addresses),
        "dns_addresses_outside_ru_inventory": sum(item["GEOIP_CATEGORY"] == "OUTSIDE_GEOIP_RU" for item in dns_addresses),
        "https_ipv4_responses": sum(item.get("https_ipv4_result") == "HTTP_RESPONSE" for item in measurements),
        "https_ipv6_responses": sum(item.get("https_ipv6_result") == "HTTP_RESPONSE" for item in measurements),
        "residential_attestation": "NOT_VERIFIED",
        "automatic_upload": False,
        "geoip_mutation": False,
        "interpretation": "The source IP is an exact-IP review lead only. Do not infer a residential CIDR or alter GeoIP data without independent origin ASN and access-network verification.",
        "inventory_rows_loaded": len(inventory_rows),
    }
    (output / "home_probe_ingest_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return result


def utc_now() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", required=True, help="local directory containing home_probe_*.json/jsonl")
    parser.add_argument("--inventory", required=True, help="complete RU/PRIVATE inventory TSV from the published GeoIP protobuf")
    parser.add_argument("--targets", default=str(DEFAULT_TARGETS))
    parser.add_argument("--output-dir", default="home-probe-ingest-output")
    parser.add_argument("--required-country", choices=("RU", "KZ", "BY"), default="RU")
    args = parser.parse_args()
    try:
        ingest_report(args)
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(f"Home probe import error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
