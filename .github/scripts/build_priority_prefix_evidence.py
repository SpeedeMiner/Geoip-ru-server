#!/usr/bin/env python3
"""Collect review-only RDAP and RPKI evidence for company-origin exceptions.

The script consumes the deterministic company-origin review queue. It never
approves, rejects, adds, or removes a prefix from DIRECT. RDAP results are
three-address samples within each selected network, not an exhaustive proof
that every address in a prefix has the same resource holder.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
import hashlib
import ipaddress
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

USER_AGENT = "Geoip-ru-prefix-audit/1.0 (+https://github.com/SpeedeMiner/Geoip-ru-server)"
RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
RPKI_BASE = "https://stat.ripe.net/data/rpki-validation/data.json"
BOOTSTRAP_URLS = {
    4: "https://data.iana.org/rdap/ipv4.json",
    6: "https://data.iana.org/rdap/ipv6.json",
}


class FetchError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def request_json(url: str, timeout: int = 30, retries: int = 3) -> tuple[int, dict[str, Any] | None, str]:
    """Fetch JSON with bounded retries; HTTP/API failures remain explicit."""
    for attempt in range(retries + 1):
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/rdap+json, application/json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                payload_bytes = response.read()
                try:
                    payload = json.loads(payload_bytes.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    return status, None, f"INVALID_JSON:{type(exc).__name__}"
                if not isinstance(payload, dict):
                    return status, None, "INVALID_JSON_ROOT"
                return status, payload, ""
        except urllib.error.HTTPError as exc:
            code = int(exc.code)
            if code in RETRYABLE_HTTP and attempt < retries:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = min(30.0, max(1.0, float(retry_after))) if retry_after else min(20.0, 2.0 ** attempt)
                except ValueError:
                    delay = min(20.0, 2.0 ** attempt)
                time.sleep(delay)
                continue
            return code, None, f"HTTP_{code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt < retries:
                time.sleep(min(20.0, 2.0 ** attempt))
                continue
            reason = getattr(exc, "reason", exc)
            return 0, None, f"NETWORK_ERROR:{type(reason).__name__}:{reason}"
    return 0, None, "RETRY_EXHAUSTED"


def read_company_queue(path: Path) -> tuple[list[dict[str, str]], str]:
    raw = path.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    header = None
    rows: list[dict[str, str]] = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        fields = next(csv.reader([line], delimiter="\t"))
        if header is None:
            header = fields
            continue
        if len(fields) != len(header):
            raise ValueError(f"{path}: malformed company review row")
        rows.append(dict(zip(header, fields)))
    if header is None or not rows:
        raise ValueError(f"{path}: empty company prefix review queue")
    required = {
        "PREFIX", "FAMILY", "COMPANY_ASNS", "LEGAL_ENTITIES",
        "GLOBAL_BGP_ORIGIN_ASNS", "GLOBAL_BGP_ORIGIN_COUNTRY_CODES",
        "GLOBAL_BGP_MOAS", "GLOBAL_BGP_OBSERVATION", "STATUS",
        "BGP_SNAPSHOT_SHA256", "BGP_SNAPSHOT_URL", "INCLUSION_BASIS",
    }
    if not required.issubset(header):
        raise ValueError(f"{path}: missing columns {sorted(required - set(header))}")

    for row in rows:
        network = ipaddress.ip_network(row["PREFIX"], strict=True)
        if row["FAMILY"] != f"IPv{network.version}":
            raise ValueError(f"family mismatch for {row['PREFIX']}")
        if row["STATUS"] != "REVIEW":
            raise ValueError(f"non-review source row: {row['PREFIX']}")
        if row["GLOBAL_BGP_OBSERVATION"] not in {"OBSERVED", "NOT_OBSERVED_STATIC_DIRECT_PIN"}:
            raise ValueError(f"unexpected BGP observation status for {row['PREFIX']}")
        if not row["BGP_SNAPSHOT_SHA256"] or not row["BGP_SNAPSHOT_URL"]:
            raise ValueError(f"missing BGP snapshot provenance for {row['PREFIX']}")

    return rows, sha256_bytes(raw)


def select_priority_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Select exact MOAS and company-only prefixes; keep their evidence source."""
    selected = []
    for row in rows:
        is_moas = row["GLOBAL_BGP_MOAS"].strip().lower() == "yes"
        is_company_only = row["INCLUSION_BASIS"] == "COMPANY_ASN_ONLY"
        if is_moas or is_company_only:
            copy = dict(row)
            reasons = []
            if is_moas:
                reasons.append("EXACT_MOAS")
            if is_company_only:
                reasons.append("COMPANY_ONLY")
            copy["PRIORITY_REASON"] = "+".join(reasons)
            copy["STATUS"] = "REVIEW"
            selected.append(copy)

    seen: set[str] = set()
    for row in selected:
        prefix = row["PREFIX"]
        if prefix in seen:
            raise ValueError(f"duplicate priority prefix {prefix}")
        seen.add(prefix)
    return sorted(selected, key=lambda row: _prefix_sort_key(row["PREFIX"]))


def _prefix_sort_key(value: str) -> tuple[int, int, int]:
    network = ipaddress.ip_network(value, strict=True)
    return network.version, int(network.network_address), network.prefixlen


def sample_addresses(prefix: str) -> list[str]:
    """First, midpoint and last address; duplicate samples are removed."""
    network = ipaddress.ip_network(prefix, strict=True)
    first = int(network.network_address)
    last = int(network.broadcast_address)
    middle = first + ((last - first) // 2)
    return [str(ipaddress.ip_address(value)) for value in dict.fromkeys((first, middle, last))]


def parse_bootstrap(family: int, payload: dict[str, Any]) -> list[tuple[ipaddress._BaseNetwork, list[str]]]:
    services = payload.get("services")
    if not isinstance(services, list):
        raise ValueError("IANA RDAP bootstrap has no services array")
    entries: list[tuple[ipaddress._BaseNetwork, list[str]]] = []
    for service in services:
        if not isinstance(service, list) or len(service) != 2:
            continue
        prefixes, urls = service
        if not isinstance(prefixes, list) or not isinstance(urls, list):
            continue
        usable_urls = [str(url) for url in urls if str(url).startswith("https://")]
        if not usable_urls:
            continue
        for raw_prefix in prefixes:
            try:
                network = ipaddress.ip_network(str(raw_prefix), strict=True)
            except ValueError:
                continue
            if network.version == family:
                entries.append((network, usable_urls))
    if not entries:
        raise ValueError(f"IANA RDAP bootstrap has no IPv{family} networks")
    return entries


def rdap_base_for_address(address: str, entries: list[tuple[ipaddress._BaseNetwork, list[str]]]) -> str:
    addr = ipaddress.ip_address(address)
    matches = [(network.prefixlen, urls) for network, urls in entries if addr in network]
    if not matches:
        raise ValueError(f"no authoritative RDAP bootstrap entry for {address}")
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1][0].rstrip("/") + "/"


def _vcard_values(entity: dict[str, Any]) -> tuple[str, str]:
    full_name = ""
    organisation = ""
    vcard = entity.get("vcardArray")
    if isinstance(vcard, list) and len(vcard) >= 2 and isinstance(vcard[1], list):
        for prop in vcard[1]:
            if not isinstance(prop, list) or len(prop) < 4:
                continue
            name = str(prop[0]).lower()
            value = prop[3]
            if name == "fn":
                full_name = str(value)
            elif name == "org":
                if isinstance(value, list):
                    organisation = " / ".join(str(part) for part in value)
                else:
                    organisation = str(value)
    return full_name, organisation


def parse_rdap_object(payload: dict[str, Any]) -> dict[str, str]:
    """Extract resource fields without assuming the registrant is the route origin."""
    ranges: list[str] = []
    for item in payload.get("cidr0_cidrs") or []:
        if not isinstance(item, dict):
            continue
        for version, key in ((4, "v4prefix"), (6, "v6prefix")):
            if key not in item or "length" not in item:
                continue
            try:
                ranges.append(ipaddress.ip_network(
                    f"{item[key]}/{int(item['length'])}", strict=True
                ).with_prefixlen)
            except (ValueError, TypeError):
                continue

    start = str(payload.get("startAddress") or "")
    end = str(payload.get("endAddress") or "")
    if start and end and not ranges:
        try:
            start_ip, end_ip = ipaddress.ip_address(start), ipaddress.ip_address(end)
            if start_ip.version == end_ip.version:
                ranges.extend(
                    network.with_prefixlen
                    for network in ipaddress.summarize_address_range(start_ip, end_ip)
                )
        except ValueError:
            pass

    entity_names: list[str] = []
    registrant_names: list[str] = []
    entity_handles: list[str] = []
    for entity in payload.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        fn, org = _vcard_values(entity)
        description = org or fn or str(entity.get("handle") or "")
        if description:
            entity_names.append(description)
            roles = {str(role).lower() for role in entity.get("roles") or []}
            if "registrant" in roles:
                registrant_names.append(description)
        if entity.get("handle"):
            entity_handles.append(str(entity["handle"]))

    return {
        "OBJECT_CLASS": str(payload.get("objectClassName") or ""),
        "HANDLE": str(payload.get("handle") or ""),
        "NAME": str(payload.get("name") or ""),
        "TYPE": str(payload.get("type") or ""),
        "COUNTRY": str(payload.get("country") or ""),
        "START_ADDRESS": start,
        "END_ADDRESS": end,
        "REGISTERED_CIDRS": ",".join(sorted(set(ranges))),
        "REGISTRANT_ENTITIES": " | ".join(sorted(set(registrant_names))),
        "ALL_ENTITIES": " | ".join(sorted(set(entity_names))),
        "ENTITY_HANDLES": ",".join(sorted(set(entity_handles))),
        "STATUS": ",".join(str(item) for item in payload.get("status") or []),
    }


def rdap_relation(prefix: str, parsed: dict[str, str]) -> str:
    requested = ipaddress.ip_network(prefix, strict=True)
    registered = []
    for value in parsed["REGISTERED_CIDRS"].split(","):
        if not value:
            continue
        try:
            registered.append(ipaddress.ip_network(value, strict=True))
        except ValueError:
            continue
    if not registered:
        return "RANGE_NOT_EXPOSED"
    if any(network == requested for network in registered):
        return "EXACT_PREFIX_MATCH"
    if any(requested.subnet_of(network) for network in registered):
        return "COVERING_RESOURCE"
    if any(network.subnet_of(requested) for network in registered):
        return "MORE_SPECIFIC_RESOURCE_AT_SAMPLE"
    return "OVERLAPPING_OR_SPLIT_RANGE"


def fetch_rdap_sample(prefix: str, address: str,
                      entries: list[tuple[ipaddress._BaseNetwork, list[str]]]) -> dict[str, str]:
    if not entries:
        return {
            "PREFIX": prefix, "SAMPLE_ADDRESS": address, "RDAP_URL": "",
            "HTTP_STATUS": "0", "QUERY_STATUS": "BOOTSTRAP_UNAVAILABLE",
            "OBJECT_CLASS": "", "HANDLE": "", "NAME": "", "TYPE": "", "COUNTRY": "",
            "START_ADDRESS": "", "END_ADDRESS": "", "REGISTERED_CIDRS": "",
            "REGISTRANT_ENTITIES": "", "ALL_ENTITIES": "", "ENTITY_HANDLES": "",
            "STATUS": "", "RDAP_PREFIX_RELATION": "NOT_AVAILABLE",
        }
    base = rdap_base_for_address(address, entries)
    encoded_address = urllib.parse.quote(address, safe=":")
    url = f"{base}ip/{encoded_address}"
    status, payload, error = request_json(url)
    row = {
        "PREFIX": prefix,
        "SAMPLE_ADDRESS": address,
        "RDAP_URL": url,
        "HTTP_STATUS": str(status),
        "QUERY_STATUS": "OK" if status == 200 and payload is not None else (error or "EMPTY_RESPONSE"),
    }
    defaults = {
        "OBJECT_CLASS": "", "HANDLE": "", "NAME": "", "TYPE": "", "COUNTRY": "",
        "START_ADDRESS": "", "END_ADDRESS": "", "REGISTERED_CIDRS": "",
        "REGISTRANT_ENTITIES": "", "ALL_ENTITIES": "", "ENTITY_HANDLES": "", "STATUS": "",
    }
    if payload is not None and status == 200:
        defaults.update(parse_rdap_object(payload))
        row.update(defaults)
        row["RDAP_PREFIX_RELATION"] = rdap_relation(prefix, defaults)
    else:
        row.update(defaults)
        row["RDAP_PREFIX_RELATION"] = "NOT_AVAILABLE"
    return row


def fetch_rpki_origin(prefix: str, asn: str) -> dict[str, str]:
    number = asn[2:] if asn.upper().startswith("AS") else asn
    query = urllib.parse.urlencode({"resource": number, "prefix": prefix})
    url = f"{RPKI_BASE}?{query}"
    status, payload, error = request_json(url)
    row = {
        "PREFIX": prefix,
        "ORIGIN_ASN": f"AS{number}",
        "RPKI_URL": url,
        "HTTP_STATUS": str(status),
        "QUERY_STATUS": "OK" if status == 200 and payload is not None else (error or "EMPTY_RESPONSE"),
        "RPKI_STATUS": "",
        "RPKI_DESCRIPTION": "",
    }
    data = payload.get("data") if payload else None
    if isinstance(data, dict):
        row["RPKI_STATUS"] = str(data.get("status") or "")
        row["RPKI_DESCRIPTION"] = str(data.get("description") or "")
        if row["QUERY_STATUS"] == "OK" and not row["RPKI_STATUS"]:
            row["QUERY_STATUS"] = "INVALID_RESPONSE_NO_STATUS"
    return row


def write_tsv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t", extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_evidence(company_queue: Path, output_dir: Path, max_workers: int = 5) -> dict[str, Any]:
    source_rows, source_sha = read_company_queue(company_queue)
    priority = select_priority_rows(source_rows)
    if len(priority) != 56:
        raise ValueError(f"expected 56 company MOAS/company-only priority prefixes, got {len(priority)}")
    moas_count = sum(row["GLOBAL_BGP_MOAS"] == "yes" for row in priority)
    company_only_count = sum(row["INCLUSION_BASIS"] == "COMPANY_ASN_ONLY" for row in priority)
    if (moas_count, company_only_count) != (52, 4):
        raise ValueError(f"unexpected priority split: MOAS={moas_count}, company_only={company_only_count}")

    bootstraps: dict[int, list[tuple[ipaddress._BaseNetwork, list[str]]]] = {}
    bootstrap_hashes: dict[int, str] = {}
    bootstrap_errors: dict[int, str] = {}
    for family, url in BOOTSTRAP_URLS.items():
        status, payload, error = request_json(url)
        if status != 200 or payload is None:
            bootstraps[family] = []
            bootstrap_hashes[family] = "UNAVAILABLE"
            bootstrap_errors[family] = error or f"HTTP_{status}"
            continue
        try:
            # Preserve exact registry bytes separately from parsed JSON for digesting.
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
            bootstraps[family] = parse_bootstrap(family, payload)
            bootstrap_hashes[family] = sha256_bytes(raw)
        except Exception as exc:
            bootstraps[family] = []
            bootstrap_hashes[family] = "UNAVAILABLE"
            bootstrap_errors[family] = f"{type(exc).__name__}:{exc}"

    output_dir.mkdir(parents=True, exist_ok=True)
    priority_columns = [
        "PREFIX", "FAMILY", "COMPANY_ASNS", "COMPANY_GROUPS", "LEGAL_ENTITIES",
        "GLOBAL_BGP_ORIGIN_ASNS", "GLOBAL_BGP_ORIGIN_COUNTRY_CODES", "GLOBAL_BGP_MOAS",
        "INCLUSION_BASIS", "PRIORITY_REASON", "GLOBAL_BGP_OBSERVATION",
        "BGP_SNAPSHOT_SHA256", "BGP_SNAPSHOT_URL", "STATUS",
    ]
    for row in priority:
        row["STATUS"] = "REVIEW"
    write_tsv(output_dir / "priority_prefixes.tsv", priority, priority_columns)

    rdap_tasks = []
    for row in priority:
        network = row["PREFIX"]
        for address in sample_addresses(network):
            rdap_tasks.append((network, address, bootstraps[ipaddress.ip_network(network).version]))

    rdap_rows: list[dict[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(fetch_rdap_sample, prefix, address, entries): (prefix, address)
            for prefix, address, entries in rdap_tasks
        }
        for future in concurrent.futures.as_completed(futures):
            prefix, address = futures[future]
            try:
                rdap_rows.append(future.result())
            except Exception as exc:  # preserve sample context; never turn it into "not registered"
                rdap_rows.append({
                    "PREFIX": prefix, "SAMPLE_ADDRESS": address, "RDAP_URL": "",
                    "HTTP_STATUS": "0", "QUERY_STATUS": f"CLIENT_ERROR:{type(exc).__name__}:{exc}",
                    "OBJECT_CLASS": "", "HANDLE": "", "NAME": "", "TYPE": "", "COUNTRY": "",
                    "START_ADDRESS": "", "END_ADDRESS": "", "REGISTERED_CIDRS": "",
                    "REGISTRANT_ENTITIES": "", "ALL_ENTITIES": "", "ENTITY_HANDLES": "",
                    "STATUS": "", "RDAP_PREFIX_RELATION": "NOT_AVAILABLE",
                })
    rdap_rows.sort(key=lambda row: (row["PREFIX"], row["SAMPLE_ADDRESS"]))
    rdap_columns = [
        "PREFIX", "SAMPLE_ADDRESS", "RDAP_URL", "HTTP_STATUS", "QUERY_STATUS",
        "OBJECT_CLASS", "HANDLE", "NAME", "TYPE", "COUNTRY", "START_ADDRESS",
        "END_ADDRESS", "REGISTERED_CIDRS", "RDAP_PREFIX_RELATION",
        "REGISTRANT_ENTITIES", "ALL_ENTITIES", "ENTITY_HANDLES", "STATUS",
    ]
    write_tsv(output_dir / "rdap_samples.tsv", rdap_rows, rdap_columns)

    rpki_tasks: list[tuple[str, str]] = []
    for row in priority:
        origin_asns = [part.strip() for part in row["GLOBAL_BGP_ORIGIN_ASNS"].split(",") if part.strip()]
        for asn in sorted(set(origin_asns)):
            rpki_tasks.append((row["PREFIX"], asn))

    rpki_rows: list[dict[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(fetch_rpki_origin, prefix, asn): (prefix, asn)
            for prefix, asn in rpki_tasks
        }
        for future in concurrent.futures.as_completed(futures):
            prefix, asn = futures[future]
            try:
                rpki_rows.append(future.result())
            except Exception as exc:
                rpki_rows.append({
                    "PREFIX": prefix, "ORIGIN_ASN": asn, "RPKI_URL": "", "HTTP_STATUS": "0",
                    "QUERY_STATUS": f"CLIENT_ERROR:{type(exc).__name__}:{exc}",
                    "RPKI_STATUS": "", "RPKI_DESCRIPTION": "",
                })
    rpki_rows.sort(key=lambda row: (row["PREFIX"], row["ORIGIN_ASN"]))
    rpki_columns = [
        "PREFIX", "ORIGIN_ASN", "RPKI_URL", "HTTP_STATUS", "QUERY_STATUS",
        "RPKI_STATUS", "RPKI_DESCRIPTION",
    ]
    write_tsv(output_dir / "rpki_by_origin.tsv", rpki_rows, rpki_columns)

    status_counts = collections.Counter(row["RPKI_STATUS"] or row["QUERY_STATUS"] for row in rpki_rows)
    rdap_status_counts = collections.Counter(row["QUERY_STATUS"] for row in rdap_rows)
    prefix_rdap_groups: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for row in rdap_rows:
        if row["PREFIX"]:
            prefix_rdap_groups[row["PREFIX"]].append(row)
    rdap_consistency = collections.Counter()
    for prefix, samples in prefix_rdap_groups.items():
        success = [row for row in samples if row["QUERY_STATUS"] == "OK"]
        handles = {row["HANDLE"] or row["NAME"] or row["REGISTERED_CIDRS"] for row in success}
        if len(success) != len(samples):
            rdap_consistency["INCOMPLETE_SAMPLES"] += 1
        elif len(handles) > 1:
            rdap_consistency["MULTIPLE_RESOURCE_OBJECTS_AT_SAMPLES"] += 1
        elif any(row["RDAP_PREFIX_RELATION"] == "EXACT_PREFIX_MATCH" for row in success):
            rdap_consistency["SAMPLED_RESOURCE_EXACT_PREFIX"] += 1
        elif any(row["RDAP_PREFIX_RELATION"] == "MORE_SPECIFIC_RESOURCE_AT_SAMPLE" for row in success):
            rdap_consistency["MORE_SPECIFIC_RESOURCE_AT_SAMPLE"] += 1
        else:
            rdap_consistency["ONE_COVERING_OR_UNCLASSIFIED_RESOURCE_AT_SAMPLES"] += 1

    stats = [
        "Priority prefix evidence report (review only)",
        f"Source company review queue SHA256: {source_sha}",
        f"IANA IPv4 RDAP bootstrap URL: {BOOTSTRAP_URLS[4]}",
        f"IANA IPv4 RDAP bootstrap SHA256: {bootstrap_hashes[4]}",
        f"IANA IPv4 RDAP bootstrap status: {bootstrap_errors.get(4, 'OK')}",
        f"IANA IPv6 RDAP bootstrap URL: {BOOTSTRAP_URLS[6]}",
        f"IANA IPv6 RDAP bootstrap SHA256: {bootstrap_hashes[6]}",
        f"IANA IPv6 RDAP bootstrap status: {bootstrap_errors.get(6, 'OK')}",
        f"Priority prefixes: {len(priority)}",
        f"Exact MOAS prefixes: {moas_count}",
        f"Company-only prefixes: {company_only_count}",
        f"RDAP sample queries attempted: {len(rdap_tasks)}",
        f"RDAP sample query statuses: {dict(sorted(rdap_status_counts.items()))}",
        f"RPKI origin-prefix checks attempted: {len(rpki_tasks)}",
        f"RPKI query/status counts: {dict(sorted(status_counts.items()))}",
        f"RDAP per-prefix sample consistency: {dict(sorted(rdap_consistency.items()))}",
        "RDAP requests use IANA bootstrap longest-prefix selection and sample first/mid/last addresses.",
        "RDAP observations describe the registry's most-specific network containing each sample address; they do not prove every address in a prefix has the same holder.",
        "RPKI status is queried per exact prefix/origin ASN pair using RIPE NCC Routinator; valid means ROA authorises the pair, not that the ASN legally owns the resource.",
        "HTTP/network errors remain explicit query errors and are not converted to UNKNOWN, absent, or no-owner results.",
        "IRR has not yet been queried by this stage; no route-object absence or presence is inferred.",
        "Every prefix remains STATUS=REVIEW; this artifact does not change DIRECT policy, main, release, or geoip_RU.dat.",
    ]
    (output_dir / "priority_prefix_evidence_stats.txt").write_text("\n".join(stats) + "\n", encoding="utf-8")
    (output_dir / "priority_prefix_evidence_README.txt").write_text(
        "\n".join(stats) + "\n", encoding="utf-8"
    )
    return {
        "priority_prefixes": len(priority),
        "moas_prefixes": moas_count,
        "company_only_prefixes": company_only_count,
        "rdap_samples": len(rdap_rows),
        "rdap_query_statuses": dict(sorted(rdap_status_counts.items())),
        "rpki_origin_checks": len(rpki_rows),
        "rpki_statuses": dict(sorted(status_counts.items())),
        "bootstrap_sha256": bootstrap_hashes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    try:
        result = build_evidence(args.company_review, args.output_dir, args.workers)
    except (OSError, ValueError, FetchError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
