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


IRR_METADATA_URL = "https://rest.db.ripe.net/metadata/sources.json"
IRR_SEARCH_URL = "https://rest.db.ripe.net/search"
DOCUMENTED_GRS_SOURCES = ("AFRINIC-GRS", "APNIC-GRS", "ARIN-GRS", "JPIRR-GRS", "LACNIC-GRS", "RADB-GRS", "RIPE-GRS")


def _source_list_from_metadata(payload: dict[str, Any]) -> list[str]:
    """Read the live RIPE metadata WhoisResources JSON schema.

    The production endpoint places supported sources in sources.source.
    Some older examples expose GRS-only entries in a separate grs-sources key,
    so both shapes are accepted. Returned names come from the server metadata.
    """
    values: set[str] = set()

    def collect(container: Any) -> None:
        if not isinstance(container, dict):
            return
        sources = container.get("source", [])
        if isinstance(sources, dict):
            sources = [sources]
        for item in sources if isinstance(sources, list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("id") or "").strip()
            if name:
                values.add(name.upper())

    collect(payload.get("sources"))
    collect(payload.get("grs-sources") or payload.get("grsSources"))
    values.add("RIPE")
    return sorted(values)

def _object_attributes(obj: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = collections.defaultdict(list)
    for section in ("primary-key", "attributes"):
        container = obj.get(section) or {}
        attributes = container.get("attribute", []) if isinstance(container, dict) else []
        if isinstance(attributes, dict):
            attributes = [attributes]
        for item in attributes if isinstance(attributes, list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").lower()
            value = item.get("value")
            if name and value is not None:
                result[name].append(str(value).strip())
    return dict(result)


def parse_irr_search_payload(prefix: str, payload: dict[str, Any],
                             global_origins: set[str]) -> tuple[str, list[dict[str, str]]]:
    """Extract route/route6 objects; no object result is scoped to queried sources only."""
    errors = payload.get("errormessages") or {}
    messages = errors.get("errormessage", []) if isinstance(errors, dict) else []
    if isinstance(messages, dict):
        messages = [messages]
    error_text = []
    for item in messages if isinstance(messages, list) else []:
        if isinstance(item, dict) and str(item.get("severity", "")).lower() == "error":
            error_text.append(str(item.get("text") or "RIPE Database API error"))
    if error_text:
        return "API_ERROR_IN_BODY", []

    container = payload.get("objects") or {}
    objects = container.get("object", []) if isinstance(container, dict) else []
    if isinstance(objects, dict):
        objects = [objects]
    if not isinstance(objects, list):
        return "INVALID_OBJECTS_PAYLOAD", []

    expected = ipaddress.ip_network(prefix, strict=True)
    output: list[dict[str, str]] = []
    exact_count = 0
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        attrs = _object_attributes(obj)
        route_values = attrs.get("route", []) + attrs.get("route6", [])
        origin_values = attrs.get("origin", [])
        route_prefix = route_values[0] if route_values else ""
        try:
            route_network = ipaddress.ip_network(route_prefix, strict=True) if route_prefix else None
        except ValueError:
            route_network = None
        exact = bool(route_network and route_network == expected)
        if exact:
            exact_count += 1
        origin = origin_values[0].upper() if origin_values else ""
        if origin and origin.isdigit():
            origin = f"AS{origin}"
        if origin and not origin.startswith("AS"):
            origin = f"AS{origin}"

        source_data = obj.get("source") or {}
        source_name = str(source_data.get("id") or source_data.get("name") or "").upper() if isinstance(source_data, dict) else ""
        primary_data = obj.get("primary-key") or {}
        object_key = ""
        if isinstance(primary_data, dict):
            for item in primary_data.get("attribute", []) if isinstance(primary_data.get("attribute"), list) else []:
                if isinstance(item, dict) and str(item.get("name", "")).lower() in {"route", "route6"}:
                    object_key = str(item.get("value") or "")
                    break
        object_type = str(obj.get("type") or "")
        output.append({
            "QUERY_PREFIX": prefix,
            "OBJECT_TYPE": object_type,
            "ROUTE_PREFIX": route_prefix,
            "OBJECT_KEY": object_key,
            "ORIGIN_ASN": origin,
            "REGISTRY_SOURCE": source_name,
            "EXACT_PREFIX_MATCH": "yes" if exact else "no",
            "GLOBAL_BGP_ORIGIN_MATCH": "yes" if origin in global_origins else "no",
            "MNT_BY": " | ".join(attrs.get("mnt-by", [])),
            "ORG": " | ".join(attrs.get("org", [])),
            "DESCR": " | ".join(attrs.get("descr", [])),
            "REMARKS": " | ".join(attrs.get("remarks", [])),
            "MEMBER_OF": " | ".join(attrs.get("member-of", [])),
            "CREATED": " | ".join(attrs.get("created", [])),
            "LAST_MODIFIED": " | ".join(attrs.get("last-modified", [])),
        })
    if not output:
        return "NO_OBJECTS_IN_QUERIED_SOURCES", []
    if exact_count == 0:
        return "NO_EXACT_ROUTE_OBJECT_IN_QUERY_RESULTS", output
    return "OK", output


def fetch_irr_prefix(prefix: str, sources: list[str],
                     global_origins: set[str]) -> tuple[str, str, list[dict[str, str]]]:
    network = ipaddress.ip_network(prefix, strict=True)
    params: list[tuple[str, str]] = []
    for source in sources:
        params.append(("source", source))
    params.append(("query-string", prefix))
    params.append(("type-filter", "route" if network.version == 4 else "route6"))
    params.append(("flags", "no-referenced"))
    params.append(("limit", "1000"))
    url = f"{IRR_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    status, payload, error = request_json(url)
    if status == 404:
        return "NO_OBJECTS_IN_QUERIED_SOURCES", url, []
    if status != 200 or payload is None:
        return error or f"HTTP_{status}", url, []
    query_status, rows = parse_irr_search_payload(prefix, payload, global_origins)
    return query_status, url, rows


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

    # RIPE Database GRS snapshots expose multiple regional IRR data sources.
    # Their scope is explicit in the output and is not claimed to be the entire IRR ecosystem.
    metadata_status, metadata_payload, metadata_error = request_json(IRR_METADATA_URL)
    if metadata_status == 200 and metadata_payload is not None:
        metadata_sources = _source_list_from_metadata(metadata_payload)
        irr_metadata_sha = sha256_bytes(
            json.dumps(metadata_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        irr_metadata_status = "OK"
        (output_dir / "irr_sources_metadata.json").write_text(
            json.dumps(metadata_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\\n",
            encoding="utf-8",
        )
    else:
        metadata_sources = ["RIPE"]
        irr_metadata_sha = "UNAVAILABLE"
        irr_metadata_status = metadata_error or f"HTTP_{metadata_status}"
        (output_dir / "irr_sources_metadata.json").write_text(
            json.dumps({"query_status": irr_metadata_status}, ensure_ascii=False, sort_keys=True, indent=2) + "\\n",
            encoding="utf-8",
        )
    # Metadata deployments may omit the GRS list even though the RIPE Database
    # REST API documents these GRS sources for search queries; query them explicitly.
    irr_sources = sorted(set(metadata_sources + list(DOCUMENTED_GRS_SOURCES)))

    irr_prefix_rows: list[dict[str, str]] = []
    irr_object_rows: list[dict[str, str]] = []
    irr_query_statuses: collections.Counter[str] = collections.Counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                fetch_irr_prefix,
                row["PREFIX"],
                irr_sources,
                {part.strip() for part in row["GLOBAL_BGP_ORIGIN_ASNS"].split(",") if part.strip()},
            ): row["PREFIX"]
            for row in priority
        }
        for future in concurrent.futures.as_completed(futures):
            prefix = futures[future]
            try:
                query_status, query_url, objects = future.result()
            except Exception as exc:
                query_status, query_url, objects = f"CLIENT_ERROR:{type(exc).__name__}:{exc}", "", []
            irr_query_statuses[query_status] += 1
            irr_object_rows.extend(objects)
            exact_objects = [obj for obj in objects if obj["EXACT_PREFIX_MATCH"] == "yes"]
            matching_objects = [obj for obj in exact_objects if obj["GLOBAL_BGP_ORIGIN_MATCH"] == "yes"]
            irr_prefix_rows.append({
                "PREFIX": prefix,
                "QUERY_STATUS": query_status,
                "QUERY_URL": query_url,
                "QUERY_SCOPE_SOURCES": ",".join(irr_sources),
                "IRR_EXACT_OBJECTS": str(len(exact_objects)),
                "IRR_EXACT_BGP_ORIGIN_MATCH_OBJECTS": str(len(matching_objects)),
                "IRR_EXACT_OBJECT_SOURCES": " | ".join(sorted({obj["REGISTRY_SOURCE"] for obj in exact_objects if obj["REGISTRY_SOURCE"]})),
                "IRR_EXACT_ORIGINS": " | ".join(sorted({obj["ORIGIN_ASN"] for obj in exact_objects if obj["ORIGIN_ASN"]})),
                "IRR_MATCHED_BGP_ORIGINS": " | ".join(sorted({obj["ORIGIN_ASN"] for obj in matching_objects if obj["ORIGIN_ASN"]})),
                "IRR_MNT_BY": " | ".join(sorted({obj["MNT_BY"] for obj in exact_objects if obj["MNT_BY"]})),
                "IRR_ORG": " | ".join(sorted({obj["ORG"] for obj in exact_objects if obj["ORG"]})),
                "IRR_DESCR": " | ".join(sorted({obj["DESCR"] for obj in exact_objects if obj["DESCR"]})),
                "STATUS": "REVIEW",
                "INTERPRETATION": "Search limited to RIPE Database plus its reported GRS sources; not a global search of every independent IRR.",
            })

    irr_prefix_rows.sort(key=lambda row: row["PREFIX"])
    irr_object_rows.sort(key=lambda row: (
        row["QUERY_PREFIX"], row["REGISTRY_SOURCE"], row["ORIGIN_ASN"], row["ROUTE_PREFIX"]
    ))
    write_tsv(output_dir / "irr_prefix_summary.tsv", irr_prefix_rows, [
        "PREFIX", "QUERY_STATUS", "QUERY_URL", "QUERY_SCOPE_SOURCES",
        "IRR_EXACT_OBJECTS", "IRR_EXACT_BGP_ORIGIN_MATCH_OBJECTS",
        "IRR_EXACT_OBJECT_SOURCES", "IRR_EXACT_ORIGINS", "IRR_MATCHED_BGP_ORIGINS",
        "IRR_MNT_BY", "IRR_ORG", "IRR_DESCR", "STATUS", "INTERPRETATION",
    ])
    write_tsv(output_dir / "irr_route_objects.tsv", irr_object_rows, [
        "QUERY_PREFIX", "OBJECT_TYPE", "ROUTE_PREFIX", "OBJECT_KEY", "ORIGIN_ASN",
        "REGISTRY_SOURCE", "EXACT_PREFIX_MATCH", "GLOBAL_BGP_ORIGIN_MATCH",
        "MNT_BY", "ORG", "DESCR", "REMARKS", "MEMBER_OF", "CREATED", "LAST_MODIFIED",
    ])

    status_counts = collections.Counter(row["RPKI_STATUS"] or row["QUERY_STATUS"] for row in rpki_rows)
    rdap_status_counts = collections.Counter(row["QUERY_STATUS"] for row in rdap_rows)
    prefix_rdap_groups: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for row in rdap_rows:
        if row["PREFIX"]:
            prefix_rdap_groups[row["PREFIX"]].append(row)
    rdap_consistency = collections.Counter()
    summary_rows: list[dict[str, str]] = []
    for priority_row in priority:
        prefix = priority_row["PREFIX"]
        samples = prefix_rdap_groups.get(prefix, [])
        success = [row for row in samples if row["QUERY_STATUS"] == "OK"]
        resources = {
            (
                row["HANDLE"],
                row["NAME"],
                row["REGISTERED_CIDRS"],
                row["REGISTRANT_ENTITIES"],
            )
            for row in success
        }
        if len(success) != len(samples):
            consistency = "INCOMPLETE_SAMPLES"
        elif len(resources) > 1:
            consistency = "MULTIPLE_RESOURCE_OBJECTS_AT_SAMPLES"
        elif any(row["RDAP_PREFIX_RELATION"] == "EXACT_PREFIX_MATCH" for row in success):
            consistency = "SAMPLED_RESOURCE_EXACT_PREFIX"
        elif any(row["RDAP_PREFIX_RELATION"] == "MORE_SPECIFIC_RESOURCE_AT_SAMPLE" for row in success):
            consistency = "MORE_SPECIFIC_RESOURCE_AT_SAMPLE"
        else:
            consistency = "ONE_COVERING_OR_UNCLASSIFIED_RESOURCE_AT_SAMPLES"
        rdap_consistency[consistency] += 1
        summary_rows.append({
            "PREFIX": prefix,
            "PRIORITY_REASON": priority_row["PRIORITY_REASON"],
            "COMPANY_ASNS": priority_row["COMPANY_ASNS"],
            "GLOBAL_BGP_ORIGIN_ASNS": priority_row["GLOBAL_BGP_ORIGIN_ASNS"],
            "GLOBAL_BGP_ORIGIN_COUNTRY_CODES": priority_row["GLOBAL_BGP_ORIGIN_COUNTRY_CODES"],
            "GLOBAL_BGP_MOAS": priority_row["GLOBAL_BGP_MOAS"],
            "RDAP_SAMPLE_COUNT": str(len(samples)),
            "RDAP_SUCCESS_COUNT": str(len(success)),
            "RDAP_SAMPLE_CONSISTENCY": consistency,
            "RDAP_RESOURCE_HANDLES": " | ".join(sorted({row["HANDLE"] for row in success if row["HANDLE"]})),
            "RDAP_RESOURCE_NAMES": " | ".join(sorted({row["NAME"] for row in success if row["NAME"]})),
            "RDAP_REGISTRANT_ENTITIES": " | ".join(sorted({
                row["REGISTRANT_ENTITIES"] for row in success if row["REGISTRANT_ENTITIES"]
            })),
            "RDAP_COUNTRIES": ",".join(sorted({row["COUNTRY"] for row in success if row["COUNTRY"]})),
            "RDAP_REGISTERED_CIDRS": " | ".join(sorted({
                row["REGISTERED_CIDRS"] for row in success if row["REGISTERED_CIDRS"]
            })),
            "RDAP_QUERY_ERRORS": " | ".join(sorted({
                row["QUERY_STATUS"] for row in samples if row["QUERY_STATUS"] != "OK"
            })),
            "STATUS": "REVIEW",
            "INTERPRETATION": "Three address samples only; not exhaustive proof of every resource holder within the prefix.",
        })

    summary_columns = [
        "PREFIX", "PRIORITY_REASON", "COMPANY_ASNS", "GLOBAL_BGP_ORIGIN_ASNS",
        "GLOBAL_BGP_ORIGIN_COUNTRY_CODES", "GLOBAL_BGP_MOAS", "RDAP_SAMPLE_COUNT",
        "RDAP_SUCCESS_COUNT", "RDAP_SAMPLE_CONSISTENCY", "RDAP_RESOURCE_HANDLES",
        "RDAP_RESOURCE_NAMES", "RDAP_REGISTRANT_ENTITIES", "RDAP_COUNTRIES",
        "RDAP_REGISTERED_CIDRS", "RDAP_QUERY_ERRORS", "STATUS", "INTERPRETATION",
    ]
    write_tsv(output_dir / "prefix_holder_review_summary.tsv", summary_rows, summary_columns)

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
        f"IRR metadata source list status: {irr_metadata_status}",
        f"IRR metadata canonical SHA256: {irr_metadata_sha}",
        f"IRR metadata sources reported: {','.join(metadata_sources)}",
        f"IRR sources queried: {','.join(irr_sources)}",
        f"Documented GRS sources included: {','.join(DOCUMENTED_GRS_SOURCES)}",
        f"IRR exact-prefix search query statuses: {dict(sorted(irr_query_statuses.items()))}",
        f"IRR exact route objects returned: {sum(1 for row in irr_object_rows if row['EXACT_PREFIX_MATCH'] == 'yes')}",
        f"IRR exact prefix+observed-origin matches: {sum(1 for row in irr_object_rows if row['EXACT_PREFIX_MATCH'] == 'yes' and row['GLOBAL_BGP_ORIGIN_MATCH'] == 'yes')}",
        f"RDAP per-prefix sample consistency: {dict(sorted(rdap_consistency.items()))}",
        "RDAP requests use IANA bootstrap longest-prefix selection and sample first/mid/last addresses.",
        "RDAP observations describe the registry's most-specific network containing each sample address; they do not prove every address in a prefix has the same holder.",
        "RPKI status is queried per exact prefix/origin ASN pair using RIPE NCC Routinator; valid means ROA authorises the pair, not that the ASN legally owns the resource.",
        "HTTP/network errors remain explicit query errors and are not converted to UNKNOWN, absent, or no-owner results.",
        "IRR evidence is queried through the RIPE Database REST search using RIPE plus six GRS sources documented by the RIPE Database API; independent IRR services outside that scope are not covered.",
        "The metadata source list is archived separately; each GRS query status remains explicit because a documented source may be unavailable in a particular service deployment.",
        "A missing route object in the queried RIPE/GRS sources is not proof that no IRR route object exists anywhere.",
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
        "irr_query_statuses": dict(sorted(irr_query_statuses.items())),
        "irr_exact_route_objects": sum(1 for row in irr_object_rows if row["EXACT_PREFIX_MATCH"] == "yes"),
        "irr_exact_origin_matches": sum(1 for row in irr_object_rows if row["EXACT_PREFIX_MATCH"] == "yes" and row["GLOBAL_BGP_ORIGIN_MATCH"] == "yes"),
        "irr_sources": irr_sources,
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
