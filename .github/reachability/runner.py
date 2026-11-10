#!/usr/bin/env python3
"""Review-only RU/KZ/BY reachability collector for Geoip-ru-server.

The complete RU/PRIVATE CIDR inventory is produced separately from the
published GeoIP protobuf. Active checks are limited to declared service
endpoints and Globalping's currently online eyeball-network probes.
No result in this tool changes geoip_RU.dat.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
import datetime as dt
import ipaddress
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

GLOBALPING_API = "https://api.globalping.io/v1"
OONI_API = "https://api.ooni.io/api/v1"
RIPE_ATLAS_API = "https://atlas.ripe.net/api/v2"
COUNTRIES = {"RU", "KZ", "BY"}
USER_AGENT = "Geoip-ru-server-reachability/1.0"
DEFAULT_GLOBALPING_BUDGET = 180
DEFAULT_RIPE_BUDGET = 18


class APIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def request_json(
    url: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 25,
) -> tuple[int, dict[str, Any] | list[Any], dict[str, str]]:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    globalping_token = os.environ.get("GLOBALPING_TOKEN", "").strip()
    if globalping_token and urllib.parse.urlparse(url).netloc == "api.globalping.io":
        request_headers["Authorization"] = f"Bearer {globalping_token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read()
            parsed = json.loads(payload.decode("utf-8")) if payload else {}
            return response.status, parsed, dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            parsed = json.loads(payload.decode("utf-8")) if payload else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = {"body": payload[:1000].decode("utf-8", "replace")}
        message = parsed.get("error", parsed.get("message", str(exc))) if isinstance(parsed, dict) else str(exc)
        raise APIError(f"HTTP {exc.code}: {message}", exc.code) from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise APIError(f"request failed: {exc}") from exc


def read_inventory(path: pathlib.Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rows: list[dict[str, str]] = []
    nets: dict[str, Any] = {
        "RU": [], "PRIVATE": [],
        "_RU_LOOKUP": set(), "_PRIVATE_LOOKUP": set(),
    }
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        expected = ["CATEGORY", "PREFIX", "FAMILY", "ADDRESS_COUNT"]
        if reader.fieldnames != expected:
            raise ValueError(f"Unexpected inventory schema: {reader.fieldnames!r}")
        seen: set[tuple[str, str]] = set()
        for row in reader:
            category = row["CATEGORY"].strip().upper()
            if category not in nets:
                raise ValueError(f"Unexpected GeoIP category: {category}")
            network = ipaddress.ip_network(row["PREFIX"], strict=True)
            if (category, network.with_prefixlen) in seen:
                raise ValueError(f"Duplicate {category} prefix: {network}")
            seen.add((category, network.with_prefixlen))
            family = f"IPv{network.version}"
            if row["FAMILY"] != family or int(row["ADDRESS_COUNT"]) != network.num_addresses:
                raise ValueError(f"Invalid family/address count for {network}")
            normalized = dict(row)
            normalized["CATEGORY"] = category
            rows.append(normalized)
            nets[category].append(network)
            nets[f"_{category}_LOOKUP"].add(network.with_prefixlen)
    if not nets["RU"] or not nets["PRIVATE"]:
        raise ValueError("Inventory must contain non-empty RU and PRIVATE categories")
    for direct in nets["RU"]:
        for private in nets["PRIVATE"]:
            if direct.version == private.version and direct.overlaps(private):
                raise ValueError(f"RU/PRIVATE overlap: {direct} intersects {private}")
    return rows, nets


def map_address(
    address: str | None,
    networks: dict[str, Any],
) -> tuple[str, str]:
    """Map a service's observed IP to the most-specific GeoIP inventory entry."""
    if not address:
        return "NO_RESOLVED_ADDRESS", ""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return "INVALID_ADDRESS", ""
    # Longest-prefix lookup against O(1) string sets. The inventory may contain
    # tens of thousands of prefixes; scanning the full list for each address
    # would make endpoint-to-CIDR mapping unnecessarily expensive.
    private_lookup = networks.get("_PRIVATE_LOOKUP")
    ru_lookup = networks.get("_RU_LOOKUP")
    if private_lookup is None:
        private_lookup = {item.with_prefixlen for item in networks["PRIVATE"]}
    if ru_lookup is None:
        ru_lookup = {item.with_prefixlen for item in networks["RU"]}
    for prefix_len in range(ip.max_prefixlen, -1, -1):
        candidate = ipaddress.ip_network((ip, prefix_len), strict=False).with_prefixlen
        if candidate in private_lookup:
            return "PRIVATE", candidate
        if candidate in ru_lookup:
            return "RU", candidate
    return "OUTSIDE_GEOIP_RU", ""


def load_targets(path: pathlib.Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported targets schema_version")
    if set(data.get("countries", [])) != COUNTRIES:
        raise ValueError("Targets country scope must be exactly RU, KZ, BY")
    targets = data.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("Target catalogue is empty")
    seen: set[str] = set()
    for target in targets:
        target_id = target.get("id", "")
        domain = target.get("domain", "")
        if not target_id or target_id in seen:
            raise ValueError(f"Missing or duplicate target id: {target_id!r}")
        seen.add(target_id)
        if not domain or "/" in domain or ":" in domain:
            raise ValueError(f"Target must be a hostname, not a URL/IP: {target_id}")
        if target.get("role") not in {"control", "service", "blocked_candidate"}:
            raise ValueError(f"Invalid target role: {target_id}")
        if not set(target.get("country_scope", [])).issubset(COUNTRIES):
            raise ValueError(f"Invalid country scope: {target_id}")
        port = int(target.get("port", 443))
        if not 1 <= port <= 65535:
            raise ValueError(f"Invalid port for {target_id}")
        target["port"] = port
        path_value = target.get("path", "/")
        if not isinstance(path_value, str) or not path_value.startswith("/"):
            raise ValueError(f"HTTP path must start with '/': {target_id}")
        target["path"] = path_value
    return targets


def discover_globalping_providers() -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, Any]]:
    """Return one representative online eyeball probe descriptor per country/ASN."""
    status, payload, headers = request_json(f"{GLOBALPING_API}/probes")
    if status != 200 or not isinstance(payload, list):
        raise APIError("Globalping /probes returned an unexpected response")
    providers: dict[tuple[str, int], dict[str, Any]] = {}
    for probe in payload:
        if not isinstance(probe, dict):
            continue
        tags = set(probe.get("tags") or [])
        location = probe.get("location") or {}
        country = str(location.get("country") or "").upper()
        try:
            asn = int(location.get("asn"))
        except (TypeError, ValueError):
            continue
        if country not in COUNTRIES or "eyeball-network" not in tags:
            continue
        key = (country, asn)
        providers.setdefault(key, {
            "country": country,
            "asn": asn,
            "network": location.get("network") or "",
            "city": location.get("city") or "",
            "tags": sorted(tags),
            "probe_class": "eyeball_network_unverified",
        })
    meta = {
        "http_status": status,
        "online_probe_count": len(payload),
        "eyeball_provider_count": len(providers),
        "retrieved_at": utc_now(),
        "rate_limit_headers": {
            key: value for key, value in headers.items()
            if key.lower().startswith("x-ratelimit-")
        },
    }
    return providers, meta


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_tasks(targets: list[dict[str, Any]], providers: dict[tuple[str, int], dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for target in targets:
        for country in sorted(set(target["country_scope"])):
            for (provider_country, asn), provider in sorted(providers.items()):
                if provider_country != country:
                    continue
                for family in (4, 6):
                    tasks.append({
                        "target": target, "country": country, "provider": provider,
                        "asn": asn, "ip_family": family, "kind": "HTTPS",
                    })
                    tasks.append({
                        "target": target, "country": country, "provider": provider,
                        "asn": asn, "ip_family": family, "kind": "DNS",
                        "query_type": "A" if family == 4 else "AAAA",
                    })
    tasks.sort(key=lambda item: (
        item["country"], item["asn"], item["target"]["id"], item["ip_family"], item["kind"]
    ))
    return tasks


def rotate_tasks(tasks: list[dict[str, Any]], budget: int, day: dt.date | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if budget < 1:
        raise ValueError("budget must be at least 1")
    if len(tasks) <= budget:
        return tasks, {"total_tasks": len(tasks), "selected_tasks": len(tasks), "offset": 0}
    today = day or dt.datetime.now(dt.timezone.utc).date()
    offset = (today.toordinal() * budget) % len(tasks)
    selected = [tasks[(offset + i) % len(tasks)] for i in range(budget)]
    return selected, {"total_tasks": len(tasks), "selected_tasks": len(selected), "offset": offset}



def select_fair_provider_tasks(
    tasks: list[dict[str, Any]],
    budget: int,
    day: dt.date | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select complete measurement bundles across providers before second bundles.

    A bundle is one target tested with DNS A, DNS AAAA, HTTPS IPv4 and HTTPS IPv6.
    This avoids taking a contiguous slice of a country/ASN-sorted list, which can
    starve all later countries/providers for an entire day.
    """
    if budget < 1:
        raise ValueError("budget must be at least 1")
    today = day or dt.datetime.now(dt.timezone.utc).date()
    by_provider: dict[tuple[str, int], dict[str, list[dict[str, Any]]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for task in tasks:
        key = (str(task["country"]).upper(), int(task["asn"]))
        by_provider[key][str(task["target"]["id"])].append(task)

    provider_keys = sorted(by_provider)
    if not provider_keys:
        return [], {
            "total_tasks": len(tasks), "selected_tasks": 0, "offset": 0,
            "provider_count": 0, "providers_covered": 0, "providers_uncovered": 0,
            "countries_available": [], "countries_selected": [],
            "complete_target_bundles": 0, "partial_target_bundles": 0,
        }

    provider_offset = today.toordinal() % len(provider_keys)
    provider_order = provider_keys[provider_offset:] + provider_keys[:provider_offset]
    bundle_order = (("DNS", 4), ("DNS", 6), ("HTTPS", 4), ("HTTPS", 6))
    provider_bundles: dict[tuple[str, int], list[list[dict[str, Any]]]] = {}
    for provider_index, key in enumerate(provider_order):
        target_map = by_provider[key]
        target_ids = sorted(target_map)
        target_offset = (today.toordinal() + provider_index) % len(target_ids) if target_ids else 0
        rotated_target_ids = target_ids[target_offset:] + target_ids[:target_offset]
        bundles: list[list[dict[str, Any]]] = []
        for target_id in rotated_target_ids:
            rows = target_map[target_id]
            lookup: dict[tuple[str, int], dict[str, Any]] = {}
            for row in rows:
                signature = (str(row.get("kind")), int(row.get("ip_family", 0)))
                if signature in lookup:
                    raise ValueError(f"duplicate task in provider bundle {key}/{target_id}: {signature}")
                lookup[signature] = row
            missing = set(bundle_order) - set(lookup)
            extra = set(lookup) - set(bundle_order)
            if missing or extra:
                raise ValueError(
                    f"incomplete task bundle for {key}/{target_id}: missing={sorted(missing)} extra={sorted(extra)}"
                )
            bundles.append([lookup[signature] for signature in bundle_order])
        provider_bundles[key] = bundles

    selected: list[dict[str, Any]] = []
    complete_bundles = 0
    partial_bundles = 0
    max_rounds = max((len(value) for value in provider_bundles.values()), default=0)
    for round_index in range(max_rounds):
        for key in provider_order:
            bundles = provider_bundles[key]
            if round_index >= len(bundles) or len(selected) >= budget:
                continue
            bundle = bundles[round_index]
            remaining = budget - len(selected)
            if remaining >= len(bundle):
                selected.extend(bundle)
                complete_bundles += 1
            elif remaining:
                selected.extend(bundle[:remaining])
                partial_bundles += 1
            if len(selected) >= budget:
                break
        if len(selected) >= budget:
            break

    covered_keys = {
        (str(row["country"]).upper(), int(row["asn"])) for row in selected
    }
    countries_selected = sorted({key[0] for key in covered_keys})
    meta = {
        "total_tasks": len(tasks),
        "selected_tasks": len(selected),
        "offset": provider_offset,
        "provider_count": len(provider_keys),
        "providers_covered": len(covered_keys),
        "providers_uncovered": len(provider_keys) - len(covered_keys),
        "countries_available": sorted({key[0] for key in provider_keys}),
        "countries_selected": countries_selected,
        "complete_target_bundles": complete_bundles,
        "partial_target_bundles": partial_bundles,
        "min_tasks_for_all_providers": len(provider_keys) * len(bundle_order),
    }
    return selected, meta


def globalping_probe_metadata(probe: dict[str, Any]) -> dict[str, Any]:
    """Normalize Globalping probe descriptors from both /probes and measurement results."""
    location = probe.get("location")
    if not isinstance(location, dict):
        # MeasurementResultItem.probe is a flattened ProbeLocation object.
        location = probe
    return {
        "country": str(location.get("country") or "").upper(),
        "asn": location.get("asn"),
        "network": location.get("network") or "",
        "city": location.get("city") or "",
        "tags": set(probe.get("tags") or location.get("tags") or []),
    }


def classify_globalping_result(
    expected_country: str,
    expected_asn: int,
    actual_country: str,
    actual_asn: int,
    tags: set[str],
    kind: str,
    result_status: str,
    http_status: Any = None,
    answers: list[dict[str, Any]] | None = None,
    dns_status_code: Any = None,
) -> str:
    if (actual_country != expected_country or actual_asn != expected_asn
            or "eyeball-network" not in tags):
        return "WRONG_PROBE_SELECTION"
    if kind == "HTTPS" and result_status == "finished" and isinstance(http_status, int):
        return "ACCESSIBLE"
    if kind == "DNS" and result_status == "finished":
        if answers:
            return "DNS_ANSWER"
        if dns_status_code == 3:
            return "DNS_NXDOMAIN"
        return "DNS_NO_ANSWER"
    return "INCONCLUSIVE"


def poll_globalping(measurement_id: str, max_wait: int = 40) -> dict[str, Any]:
    url = f"{GLOBALPING_API}/measurements/{urllib.parse.quote(measurement_id)}"
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        try:
            _, payload, _ = request_json(url, timeout=15)
        except APIError as exc:
            if exc.status == 429:
                time.sleep(4)
                continue
            raise
        if not isinstance(payload, dict):
            raise APIError("Globalping measurement status is not an object")
        if payload.get("status") != "in-progress":
            return payload
        time.sleep(0.65)
    raise APIError(f"Globalping measurement {measurement_id} did not finish within {max_wait}s")


def run_globalping_task(task: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target = task["target"]
    country = task["country"]
    asn = task["asn"]
    family = task["ip_family"]
    body = {
        "type": "http",
        "target": target["domain"],
        "timeout": 15,
        "locations": [{
            "country": country,
            "asn": asn,
            "tags": ["eyeball-network"],
            "limit": 1,
        }],
        "measurementOptions": {
            "protocol": "HTTPS",
            "port": target["port"],
            "ipVersion": family,
            "request": {"method": "HEAD", "path": target["path"]},
        },
    }
    base = {
        "source": "globalping",
        "country_requested": country,
        "asn_requested": asn,
        "target_id": target["id"],
        "target_domain": target["domain"],
        "target_role": target["role"],
        "port": target["port"],
        "ip_family": family,
        "measurement_kind": task["kind"],
        "query_type": task.get("query_type", ""),
        "protocol": "HTTPS" if task["kind"] == "HTTPS" else "DNS",
        "probe_class": "eyeball_network_unverified",
        "observed_at": utc_now(),
    }
    if task["kind"] == "DNS":
        body = {
            "type": "dns",
            "target": target["domain"],
            "timeout": 15,
            "locations": [{
                "country": country, "asn": asn,
                "tags": ["eyeball-network"], "limit": 1,
            }],
            "measurementOptions": {"query": {"type": task["query_type"]}},
        }
    try:
        _, created, create_headers = request_json(
            f"{GLOBALPING_API}/measurements", method="POST", body=body, timeout=25
        )
    except APIError as exc:
        status = "RATE_LIMITED" if exc.status == 429 else "API_ERROR"
        return [{**base, "result": status, "error": str(exc)}], {
            "stage": "create", "request": body, "error": str(exc),
            "http_status": exc.status,
        }
    measurement_id = str(created.get("id") or "")
    if not measurement_id:
        return [{**base, "result": "API_ERROR", "error": "missing measurement id"}], {
            "stage": "create", "request": body, "response": created,
        }
    try:
        finished = poll_globalping(measurement_id)
    except APIError as exc:
        status = "RATE_LIMITED" if exc.status == 429 else "INCONCLUSIVE"
        return [{**base, "measurement_id": measurement_id, "result": status, "error": str(exc)}], {
            "stage": "poll", "measurement_id": measurement_id, "error": str(exc),
        }

    raw_records: dict[str, Any] = {
        "stage": "result", "request": body, "create_response": created,
        "rate_limit_headers": {
            k: v for k, v in create_headers.items() if k.lower().startswith("x-ratelimit-")
        },
        "measurement": finished,
    }
    result_rows: list[dict[str, Any]] = []
    results = finished.get("results") or []
    if not results:
        result_rows.append({
            **base, "measurement_id": measurement_id,
            "result": "NO_PROBE", "error": "measurement returned no probe results",
        })
        return result_rows, raw_records

    for item in results:
        probe = item.get("probe") or {}
        probe_meta = globalping_probe_metadata(probe)
        tags = probe_meta["tags"]
        actual_country = probe_meta["country"]
        try:
            actual_asn = int(probe_meta["asn"])
        except (TypeError, ValueError):
            actual_asn = 0
        location = probe_meta
        result = item.get("result") or {}
        result_status = result.get("status", "")
        http_status = result.get("statusCode") if task["kind"] == "HTTPS" else ""
        answers = result.get("answers") or []
        resolved_values = [answer.get("value", "") for answer in answers
                           if answer.get("type") in {"A", "AAAA"} and answer.get("value")]
        if task["kind"] == "HTTPS":
            resolved = result.get("resolvedAddress") or ""
            if resolved:
                resolved_values = [resolved]
        classification = classify_globalping_result(
            country, asn, actual_country, actual_asn, tags, task["kind"],
            result_status, http_status, answers, result.get("statusCode")
        )
        address_mappings = [map_address(value, _ACTIVE_NETWORKS) for value in resolved_values]
        ru_prefixes = sorted({prefix for category, prefix in address_mappings if category == "RU"})
        categories = sorted({category for category, _ in address_mappings})
        result_rows.append({
            **base,
            "measurement_id": measurement_id,
            "probe_country": actual_country,
            "probe_asn": actual_asn,
            "probe_network": location.get("network") or "",
            "probe_city": location.get("city") or "",
            "probe_tags": "|".join(sorted(tags)),
            "target_ip": resolved_values[0] if resolved_values else "",
            "resolved_addresses": "|".join(sorted(set(resolved_values))),
            "target_ip_category": "|".join(categories),
            "matched_ru_prefix": ru_prefixes[0] if len(ru_prefixes) == 1 else "",
            "matched_ru_prefixes": "|".join(ru_prefixes),
            "result": classification,
            "globalping_result_status": result_status,
            "dns_status_code": result.get("statusCode", "") if task["kind"] == "DNS" else "",
            "http_status": http_status if http_status is not None else "",
            "error": (
                result.get("error")
                or (result.get("rawOutput", "")[:500]
                    if classification in {"INCONCLUSIVE", "DNS_NXDOMAIN", "DNS_NO_ANSWER"}
                    else "")
            ),
        })
    return result_rows, raw_records


def collect_ooni(targets: list[dict[str, Any]], providers: dict[tuple[str, int], dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect OONI web_connectivity metadata. Anomalies remain review signals."""
    rows: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []
    since = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=7)).isoformat()
    for target in targets:
        for country in sorted(set(target["country_scope"])):
            params = urllib.parse.urlencode({
                "probe_cc": country,
                "domain": target["domain"],
                "test_name": "web_connectivity",
                "since": since,
                "limit": 100,
                "order_by": "measurement_start_time",
                "order": "desc",
            })
            url = f"{OONI_API}/measurements?{params}"
            try:
                _, payload, _ = request_json(url, timeout=30)
            except APIError as exc:
                raw.append({"source": "ooni", "target_id": target["id"], "country": country, "error": str(exc)})
                rows.append({
                    "source": "ooni", "target_id": target["id"], "target_domain": target["domain"],
                    "country": country, "result": "API_ERROR", "error": str(exc),
                })
                continue
            if not isinstance(payload, dict):
                raw.append({"source": "ooni", "target_id": target["id"], "country": country, "response": payload})
                continue
            raw.append({"source": "ooni", "target_id": target["id"], "country": country, "response": payload})
            for item in payload.get("results") or []:
                anomaly = bool(item.get("anomaly"))
                confirmed = bool(item.get("confirmed"))
                observation = "CONFIRMED_ANOMALY_REVIEW" if anomaly and confirmed else (
                    "ANOMALY_REVIEW" if anomaly else "NO_ANOMALY_RECORDED"
                )
                rows.append({
                    "source": "ooni",
                    "target_id": target["id"],
                    "target_domain": target["domain"],
                    "country": str(item.get("probe_cc") or country).upper(),
                    "probe_asn": item.get("probe_asn") or "",
                    "measurement_uid": item.get("measurement_uid") or "",
                    "measurement_start_time": item.get("measurement_start_time") or "",
                    "input": item.get("input") or target["domain"],
                    "test_name": item.get("test_name") or "web_connectivity",
                    "anomaly": anomaly,
                    "confirmed": confirmed,
                    "failure": bool(item.get("failure")),
                    "result": observation,
                    "measurement_url": item.get("measurement_url") or "",
                    "classification_policy": "OONI_METADATA_ONLY_REVIEW_REQUIRED",
                })
    return rows, raw


def atlas_probe_matches(
    probe: dict[str, Any], country: str, asn: int, af: int
) -> bool:
    asn_field = "asn_v4" if af == 4 else "asn_v6"
    status = probe.get("status") or {}
    status_name = status.get("name") if isinstance(status, dict) else probe.get("status_name")
    try:
        probe_asn = int(probe.get(asn_field) or 0)
    except (TypeError, ValueError):
        return False
    return (
        probe_asn == asn
        and str(probe.get("country_code") or "").upper() == country
        and str(status_name or "").lower() == "connected"
    )


def collect_ripe_atlas(
    targets: list[dict[str, Any]],
    providers: dict[tuple[str, int], dict[str, Any]],
    budget: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create capped Atlas TLS measurements from probes verified by country and ASN."""
    api_key = os.environ.get("RIPE_ATLAS_API_KEY", "").strip()
    if not api_key:
        return [{
            "source": "ripe_atlas", "result": "SKIPPED_API_KEY_NOT_CONFIGURED",
            "note": "Set repository secret RIPE_ATLAS_API_KEY with measurement-creation permission.",
        }], []

    tasks: list[dict[str, Any]] = []
    for target in targets:
        for country in sorted(set(target["country_scope"])):
            for (provider_country, asn), provider in sorted(providers.items()):
                if provider_country == country:
                    for af in (4, 6):
                        tasks.append({"target": target, "country": country, "asn": asn, "af": af})
    tasks.sort(key=lambda x: (x["country"], x["asn"], x["target"]["id"], x["af"]))
    selected, rotation = rotate_tasks(tasks, max(1, budget))
    rows: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []
    probe_cache: dict[tuple[str, int, int], dict[str, Any] | None] = {}
    created: list[dict[str, Any]] = []

    for task in selected:
        country, asn, af = task["country"], task["asn"], task["af"]
        cache_key = (country, asn, af)
        if cache_key not in probe_cache:
            asn_field = "asn_v4" if af == 4 else "asn_v6"
            params = urllib.parse.urlencode({
                "country_code": country,
                "status_name": "Connected",
                asn_field: asn,
                "page_size": 25,
            })
            try:
                _, payload, _ = request_json(f"{RIPE_ATLAS_API}/probes/?{params}", timeout=30)
                probe_list = payload.get("results", []) if isinstance(payload, dict) else []
                candidates = []
                for probe in probe_list:
                    if atlas_probe_matches(probe, country, asn, af):
                        candidates.append(probe)
                candidates.sort(key=lambda p: int(p.get("id", 0)))
                probe_cache[cache_key] = candidates[0] if candidates else None
                raw.append({
                    "source": "ripe_atlas_probe_selection",
                    "country": country, "asn": asn, "ip_family": af,
                    "probe_count_in_first_page": len(candidates),
                    "selected_probe_id": candidates[0].get("id") if candidates else None,
                })
            except APIError as exc:
                probe_cache[cache_key] = None
                raw.append({
                    "source": "ripe_atlas_probe_selection",
                    "country": country, "asn": asn, "ip_family": af, "error": str(exc),
                })
        probe = probe_cache[cache_key]
        target = task["target"]
        if not probe:
            rows.append({
                "source": "ripe_atlas", "country_requested": country,
                "asn_requested": asn, "target_id": target["id"],
                "ip_family": af, "result": "NO_MATCHING_CONNECTED_PROBE",
            })
            continue

        probe_id = int(probe["id"])
        definition = {
            "target": target["domain"],
            "description": f"Geoip-ru-server reachability {country} AS{asn} IPv{af} {target['id']}",
            "type": "sslcert",
            "af": af,
            "port": target["port"],
            "resolve_on_probe": True,
            "is_oneoff": True,
            "is_public": False,
        }
        body = {
            "definitions": [definition],
            "probes": [{"requested": 1, "type": "probes", "value": str(probe_id)}],
            "is_oneoff": True,
        }
        try:
            _, payload, _ = request_json(
                f"{RIPE_ATLAS_API}/measurements/",
                method="POST",
                body=body,
                headers={"Authorization": f"Key {api_key}"},
                timeout=30,
            )
            ids = payload.get("measurements") or []
            measurement_id = int(ids[0]) if ids else 0
            row = {
                "source": "ripe_atlas",
                "country_requested": country,
                "asn_requested": asn,
                "probe_id": probe_id,
                "probe_country": probe.get("country_code", ""),
                "probe_asn": probe.get("asn_v4" if af == 4 else "asn_v6", ""),
                "target_id": target["id"],
                "target_domain": target["domain"],
                "ip_family": af,
                "measurement_id": measurement_id or "",
                "result": "MEASUREMENT_CREATED" if measurement_id else "API_ERROR",
                "measurement_result": "PENDING",
            }
            rows.append(row)
            if measurement_id:
                created.append({"row": row, "measurement_id": measurement_id})
            raw.append({"source": "ripe_atlas", "request": body, "response": payload})
        except APIError as exc:
            rows.append({
                "source": "ripe_atlas", "country_requested": country,
                "asn_requested": asn, "probe_id": probe_id,
                "target_id": target["id"], "ip_family": af,
                "result": "API_ERROR", "error": str(exc),
            })
            raw.append({"source": "ripe_atlas", "request": body, "error": str(exc)})

    # Atlas measurements are asynchronous. Collect results for a bounded period;
    # records still pending remain explicitly pending and can be fetched later by ID.
    pending = list(created)
    for attempt in range(6):
        if not pending:
            break
        still_pending = []
        for item in pending:
            mid = item["measurement_id"]
            try:
                _, payload, _ = request_json(
                    f"{RIPE_ATLAS_API}/measurements/{mid}/results/?format=json",
                    headers={"Authorization": f"Key {api_key}"},
                    timeout=25,
                )
                result_items = payload if isinstance(payload, list) else payload.get("results", [])
                raw.append({"source": "ripe_atlas_results", "measurement_id": mid, "response": payload})
                if result_items:
                    item["row"]["measurement_result"] = "RESULTS_AVAILABLE"
                    item["row"]["result_count"] = len(result_items)
                    item["row"]["result_excerpt"] = json.dumps(result_items[:3], ensure_ascii=False)[:1500]
                else:
                    still_pending.append(item)
            except APIError as exc:
                item["row"]["result_error"] = str(exc)
                still_pending.append(item)
            time.sleep(0.25)
        pending = still_pending
        if pending and attempt < 5:
            time.sleep(12)
    for item in pending:
        item["row"]["measurement_result"] = "PENDING_RESULTS_FETCH_BY_ID"
    rows.append({
        "source": "ripe_atlas", "result": "BUDGET",
        "total_possible_tasks": len(tasks), "selected_tasks": len(selected),
        "rotation_offset": rotation["offset"],
        "created_measurements": len(created),
        "results_still_pending": len(pending),
    })
    return rows, raw


def write_jsonl(path: pathlib.Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_tsv(path: pathlib.Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: value if value is not None else "" for key, value in row.items()})


def build_provider_report(providers: dict[tuple[str, int], dict[str, Any]], measurements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in measurements:
        try:
            key = (str(row.get("probe_country") or row.get("country_requested") or "").upper(),
                   int(row.get("probe_asn") or row.get("asn_requested") or 0))
        except (TypeError, ValueError):
            continue
        grouped[key].append(row)
    report: list[dict[str, Any]] = []
    for key, provider in sorted(providers.items()):
        rows = grouped.get(key, [])
        counts = collections.Counter(row.get("result", "") for row in rows)
        report.append({
            "COUNTRY": key[0], "ASN": key[1], "NETWORK": provider["network"],
            "CITY_SAMPLE": provider["city"], "PROBE_TAGS": "|".join(provider["tags"]),
            "PROBE_CLASS": provider["probe_class"],
            "MEASUREMENTS": len(rows), "ACCESSIBLE": counts["ACCESSIBLE"],
            "DNS_ANSWERS": counts["DNS_ANSWER"], "DNS_NXDOMAIN": counts["DNS_NXDOMAIN"],
            "DNS_NO_ANSWER": counts["DNS_NO_ANSWER"],
            "INCONCLUSIVE": counts["INCONCLUSIVE"], "NO_PROBE": counts["NO_PROBE"],
            "API_ERROR": counts["API_ERROR"], "RATE_LIMITED": counts["RATE_LIMITED"],
        })
    return report


def build_prefix_report(
    inventory_rows: list[dict[str, str]], measurements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    matched: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in measurements:
        prefixes = set(filter(None, (row.get("matched_ru_prefixes") or "").split("|")))
        if row.get("matched_ru_prefix"):
            prefixes.add(row["matched_ru_prefix"])
        for prefix in prefixes:
            matched[prefix].append(row)
    report: list[dict[str, Any]] = []
    for inv in inventory_rows:
        if inv["CATEGORY"] != "RU":
            continue
        rows = matched.get(inv["PREFIX"], [])
        accessible = sum(row.get("result") == "ACCESSIBLE" for row in rows)
        dns_answers = sum(row.get("result") == "DNS_ANSWER" for row in rows)
        inconclusive = sum(row.get("result") == "INCONCLUSIVE" for row in rows)
        unique_targets = sorted({row.get("target_id", "") for row in rows if row.get("target_id")})
        if accessible:
            status = "ENDPOINT_ACCESSIBLE_OBSERVED"
        elif dns_answers:
            status = "DNS_RESOLVED_HTTP_NOT_CONFIRMED"
        elif inconclusive:
            status = "ENDPOINT_PRESENT_INCONCLUSIVE"
        else:
            status = "NO_MATCHED_ENDPOINT"
        report.append({
            "PREFIX": inv["PREFIX"],
            "FAMILY": inv["FAMILY"],
            "ADDRESS_COUNT": inv["ADDRESS_COUNT"],
            "STATUS": status,
            "MATCHED_ENDPOINTS": len(unique_targets),
            "DNS_ANSWER_MEASUREMENTS": dns_answers,
            "ACCESSIBLE_MEASUREMENTS": accessible,
            "INCONCLUSIVE_MEASUREMENTS": inconclusive,
            "TARGET_IDS": "|".join(unique_targets),
            "POLICY": "REVIEW_ONLY_NO_GEOIP_MUTATION",
        })
    return report


def run(args: argparse.Namespace) -> int:
    global _ACTIVE_NETWORKS
    inventory_path = pathlib.Path(args.inventory)
    targets_path = pathlib.Path(args.targets)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory_rows, networks = read_inventory(inventory_path)
    _ACTIVE_NETWORKS = networks
    targets = load_targets(targets_path)
    status: dict[str, Any] = {
        "generated_at": utc_now(),
        "countries": ["RU", "KZ", "BY"],
        "source_mode": "combined",
        "inventory_prefixes": {
            category: sum(row["CATEGORY"] == category for row in inventory_rows)
            for category in ("RU", "PRIVATE")
        },
        "target_count": len(targets),
        "policy": {
            "automatic_geoip_exclusions": False,
            "private_priority": True,
            "timeout_is_blocking_evidence": False,
            "eyeball_tag_proves_residential": False,
            "prefix_status_scope": "observed service endpoints only; never all addresses in a CIDR",
        },
    }
    write_tsv(output_dir / "reachability_inventory.tsv", inventory_rows,
              ["CATEGORY", "PREFIX", "FAMILY", "ADDRESS_COUNT"])

    providers: dict[tuple[str, int], dict[str, Any]] = {}
    provider_meta: dict[str, Any] = {}
    globalping_rows: list[dict[str, Any]] = []
    globalping_raw: list[dict[str, Any]] = []
    try:
        providers, provider_meta = discover_globalping_providers()
        all_tasks = build_tasks(targets, providers)
        selected_tasks, rotation = select_fair_provider_tasks(all_tasks, args.max_globalping_tests)
        status["globalping"] = {
            **provider_meta, **rotation,
            "planned_measurements": len(selected_tasks),
            "api_budget": args.max_globalping_tests,
        }
        max_workers = min(5, max(1, len(selected_tasks)))
        status["globalping"]["max_parallel_measurements"] = max_workers
        task_iter = iter(enumerate(selected_tasks, 1))
        active: dict[concurrent.futures.Future, int] = {}
        stop_submissions = False
        completed_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            def submit_next() -> bool:
                try:
                    index, task = next(task_iter)
                except StopIteration:
                    return False
                active[executor.submit(run_globalping_task, task)] = index
                return True

            while len(active) < max_workers and submit_next():
                pass
            while active:
                done, _ = concurrent.futures.wait(
                    active, return_when=concurrent.futures.FIRST_COMPLETED
                )
                for future in done:
                    index = active.pop(future)
                    completed_count += 1
                    try:
                        rows, raw = future.result()
                    except Exception as exc:  # keep one collector failure from discarding other results
                        rows, raw = ([{
                            "source": "globalping", "result": "COLLECTOR_ERROR",
                            "task_number": index, "error": str(exc),
                        }], {"task_number": index, "error": str(exc)})
                    globalping_rows.extend(rows)
                    globalping_raw.append(raw)
                    if any(row.get("result") == "RATE_LIMITED" for row in rows):
                        stop_submissions = True
                        status["globalping"]["stopped_early"] = "RATE_LIMITED"
                if not stop_submissions:
                    while len(active) < max_workers and submit_next():
                        pass
        status["globalping"]["completed_tasks"] = completed_count
        status["globalping"]["unsubmitted_tasks"] = max(0, len(selected_tasks) - completed_count)
    except APIError as exc:
        status["globalping"] = {"status": "API_UNAVAILABLE", "error": str(exc), "http_status": exc.status}

    write_jsonl(output_dir / "globalping_measurements.jsonl", globalping_rows)
    write_jsonl(output_dir / "globalping_raw.jsonl", globalping_raw)

    ooni_rows, ooni_raw = collect_ooni(targets, providers) if args.ooni else ([], [])
    write_jsonl(output_dir / "ooni_observations.jsonl", ooni_rows)
    write_jsonl(output_dir / "ooni_raw.jsonl", ooni_raw)

    atlas_rows, atlas_raw = collect_ripe_atlas(targets, providers, args.max_ripe_measurements) if args.ripe_atlas else ([], [])
    write_jsonl(output_dir / "ripe_atlas_measurements.jsonl", atlas_rows)
    write_jsonl(output_dir / "ripe_atlas_raw.jsonl", atlas_raw)

    provider_report = build_provider_report(providers, globalping_rows)
    prefix_report = build_prefix_report(inventory_rows, globalping_rows)
    candidates = [
        row for row in globalping_rows
        if row.get("result") in {"INCONCLUSIVE", "DNS_NXDOMAIN", "DNS_NO_ANSWER",
                                  "WRONG_PROBE_SELECTION", "RATE_LIMITED", "API_ERROR"}
    ]
    write_tsv(output_dir / "reachability_by_provider.tsv", provider_report, [
        "COUNTRY", "ASN", "NETWORK", "CITY_SAMPLE", "PROBE_TAGS", "PROBE_CLASS",
        "MEASUREMENTS", "ACCESSIBLE", "DNS_ANSWERS", "DNS_NXDOMAIN", "DNS_NO_ANSWER",
        "INCONCLUSIVE", "NO_PROBE", "API_ERROR", "RATE_LIMITED",
    ])
    write_tsv(output_dir / "reachability_by_prefix.tsv", prefix_report, [
        "PREFIX", "FAMILY", "ADDRESS_COUNT", "STATUS", "MATCHED_ENDPOINTS",
        "DNS_ANSWER_MEASUREMENTS", "ACCESSIBLE_MEASUREMENTS",
        "INCONCLUSIVE_MEASUREMENTS", "TARGET_IDS", "POLICY",
    ])
    write_tsv(output_dir / "reachability_candidates.tsv", candidates, [
        "source", "observed_at", "country_requested", "probe_country", "asn_requested",
        "probe_asn", "probe_network", "target_id", "target_domain", "target_ip",
        "ip_family", "port", "result", "error", "measurement_id", "resolved_addresses",
        "matched_ru_prefix", "matched_ru_prefixes",
    ])
    status["results"] = {
        "globalping_measurements": len(globalping_rows),
        "globalping_accessible": sum(row.get("result") == "ACCESSIBLE" for row in globalping_rows),
        "globalping_dns_answers": sum(row.get("result") == "DNS_ANSWER" for row in globalping_rows),
        "globalping_inconclusive": sum(row.get("result") == "INCONCLUSIVE" for row in globalping_rows),
        "ooni_observations": len(ooni_rows),
        "ooni_anomaly_review": sum("ANOMALY_REVIEW" in str(row.get("result", "")) for row in ooni_rows),
        "ripe_atlas_records": len(atlas_rows),
        "ru_prefixes_with_accessible_endpoint": sum(row["STATUS"] == "ENDPOINT_ACCESSIBLE_OBSERVED" for row in prefix_report),
        "ru_prefixes_with_dns_only_observation": sum(row["STATUS"] == "DNS_RESOLVED_HTTP_NOT_CONFIRMED" for row in prefix_report),
        "ru_prefixes_with_inconclusive_endpoint": sum(row["STATUS"] == "ENDPOINT_PRESENT_INCONCLUSIVE" for row in prefix_report),
        "ru_prefixes_without_matched_endpoint": sum(row["STATUS"] == "NO_MATCHED_ENDPOINT" for row in prefix_report),
    }
    (output_dir / "reachability_summary.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="TSV exported from geoip_RU.dat")
    parser.add_argument("--targets", default=".github/reachability/targets.json")
    parser.add_argument("--output-dir", default="reachability-output")
    parser.add_argument("--max-globalping-tests", type=int, default=DEFAULT_GLOBALPING_BUDGET)
    parser.add_argument("--max-ripe-measurements", type=int, default=DEFAULT_RIPE_BUDGET)
    parser.add_argument("--ooni", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--ripe-atlas", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    if args.max_globalping_tests > 220:
        parser.error("max-globalping-tests must be <=220 (unauthenticated API safety margin)")
    if args.max_globalping_tests < 1 or args.max_ripe_measurements < 1:
        parser.error("measurement budgets must be positive")
    try:
        return run(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"reachability error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
