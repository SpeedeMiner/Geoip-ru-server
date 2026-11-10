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


def read_inventory(path: pathlib.Path) -> tuple[list[dict[str, str]], dict[str, list[ipaddress._BaseNetwork]]]:
    rows: list[dict[str, str]] = []
    nets: dict[str, list[ipaddress._BaseNetwork]] = {"RU": [], "PRIVATE": []}
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
    if not nets["RU"] or not nets["PRIVATE"]:
        raise ValueError("Inventory must contain non-empty RU and PRIVATE categories")
    for direct in nets["RU"]:
        for private in nets["PRIVATE"]:
            if direct.version == private.version and direct.overlaps(private):
                raise ValueError(f"RU/PRIVATE overlap: {direct} intersects {private}")
    return rows, nets


def map_address(
    address: str | None,
    networks: dict[str, list[ipaddress._BaseNetwork]],
) -> tuple[str, str]:
    """Map a service's observed IP to the most-specific GeoIP inventory entry."""
    if not address:
        return "NO_RESOLVED_ADDRESS", ""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return "INVALID_ADDRESS", ""
    # Exact-prefix lookup from most-specific to least-specific.
    for prefix_len in range(ip.max_prefixlen, -1, -1):
        candidate = ipaddress.ip_network((ip, prefix_len), strict=False)
        if candidate in networks["PRIVATE"]:
            return "PRIVATE", candidate.with_prefixlen
        if candidate in networks["RU"]:
            return "RU", candidate.with_prefixlen
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
                        "target": target,
                        "country": country,
                        "provider": provider,
                        "asn": asn,
                        "ip_family": family,
                    })
    tasks.sort(key=lambda item: (
        item["country"], item["asn"], item["target"]["id"], item["ip_family"]
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
        "protocol": "HTTPS",
        "probe_class": "eyeball_network_unverified",
        "observed_at": utc_now(),
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
        location = probe.get("location") or {}
        tags = set(probe.get("tags") or [])
        actual_country = str(location.get("country") or "").upper()
        try:
            actual_asn = int(location.get("asn"))
        except (TypeError, ValueError):
            actual_asn = 0
        result = item.get("result") or {}
        result_status = result.get("status", "")
        resolved = result.get("resolvedAddress") or ""
        http_status = result.get("statusCode")
        if actual_country != country or actual_asn != asn or "eyeball-network" not in tags:
            classification = "WRONG_PROBE_SELECTION"
        elif result_status == "finished" and isinstance(http_status, int):
            # Any actual HTTP response (including 4xx/5xx) demonstrates that
            # DNS/TCP/TLS/HTTP reached the target. It is not a service-health verdict.
            classification = "ACCESSIBLE"
        else:
            # Timeouts, resets, TLS errors and probe-side failures are not proof of blocking.
            classification = "INCONCLUSIVE"
        ip_category, matched_prefix = map_address(resolved, _ACTIVE_NETWORKS)
        result_rows.append({
            **base,
            "measurement_id": measurement_id,
            "probe_country": actual_country,
            "probe_asn": actual_asn,
            "probe_network": location.get("network") or "",
            "probe_city": location.get("city") or "",
            "probe_tags": "|".join(sorted(tags)),
            "target_ip": resolved,
            "target_ip_category": ip_category,
            "matched_ru_prefix": matched_prefix,
            "result": classification,
            "globalping_result_status": result_status,
            "http_status": http_status if http_status is not None else "",
            "error": result.get("error") or result.get("rawOutput", "")[:500],
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


def collect_ripe_atlas(
    targets: list[dict[str, Any]],
    providers: dict[tuple[str, int], dict[str, Any]],
    budget: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create a capped set of one-off Atlas TLS-certificate measurements."""
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
    for task in selected:
        target = task["target"]
        definition = {
            "target": target["domain"],
            "description": f"Geoip-ru-server reachability {task['country']} AS{task['asn']} IPv{task['af']} {target['id']}",
            "type": "sslcert",
            "af": task["af"],
            "port": target["port"],
            "resolve_on_probe": True,
        }
        body = {
            "definitions": [definition],
            "probes": [{"requested": 1, "type": "asn", "value": task["asn"]}],
            "is_oneoff": True,
            "is_public": False,
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
            rows.append({
                "source": "ripe_atlas",
                "country_requested": task["country"],
                "asn_requested": task["asn"],
                "target_id": target["id"],
                "target_domain": target["domain"],
                "ip_family": task["af"],
                "measurement_id": ids[0] if ids else "",
                "result": "MEASUREMENT_CREATED" if ids else "API_ERROR",
                "note": "One-off SSL certificate measurement; result collection is a later extension.",
            })
            raw.append({"source": "ripe_atlas", "request": body, "response": payload})
        except APIError as exc:
            rows.append({
                "source": "ripe_atlas",
                "country_requested": task["country"],
                "asn_requested": task["asn"],
                "target_id": target["id"],
                "ip_family": task["af"],
                "result": "API_ERROR",
                "error": str(exc),
            })
            raw.append({"source": "ripe_atlas", "request": body, "error": str(exc)})
    rows.append({
        "source": "ripe_atlas", "result": "BUDGET",
        "total_possible_tasks": len(tasks), "selected_tasks": len(selected),
        "rotation_offset": rotation["offset"],
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
            "INCONCLUSIVE": counts["INCONCLUSIVE"], "NO_PROBE": counts["NO_PROBE"],
            "API_ERROR": counts["API_ERROR"], "RATE_LIMITED": counts["RATE_LIMITED"],
        })
    return report


def build_prefix_report(
    inventory_rows: list[dict[str, str]], measurements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    matched: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in measurements:
        prefix = row.get("matched_ru_prefix")
        if prefix:
            matched[prefix].append(row)
    report: list[dict[str, Any]] = []
    for inv in inventory_rows:
        if inv["CATEGORY"] != "RU":
            continue
        rows = matched.get(inv["PREFIX"], [])
        accessible = sum(row.get("result") == "ACCESSIBLE" for row in rows)
        inconclusive = sum(row.get("result") == "INCONCLUSIVE" for row in rows)
        unique_targets = sorted({row.get("target_id", "") for row in rows if row.get("target_id")})
        if accessible:
            status = "ENDPOINT_ACCESSIBLE_OBSERVED"
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
        selected_tasks, rotation = rotate_tasks(all_tasks, args.max_globalping_tests)
        status["globalping"] = {
            **provider_meta, **rotation,
            "planned_measurements": len(selected_tasks),
            "api_budget": args.max_globalping_tests,
        }
        for index, task in enumerate(selected_tasks, 1):
            rows, raw = run_globalping_task(task)
            globalping_rows.extend(rows)
            globalping_raw.append(raw)
            if any(row.get("result") == "RATE_LIMITED" for row in rows):
                status["globalping"]["stopped_early"] = "RATE_LIMITED"
                status["globalping"]["completed_tasks"] = index
                break
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
        if row.get("result") in {"INCONCLUSIVE", "WRONG_PROBE_SELECTION", "RATE_LIMITED", "API_ERROR"}
    ]
    write_tsv(output_dir / "reachability_by_provider.tsv", provider_report, [
        "COUNTRY", "ASN", "NETWORK", "CITY_SAMPLE", "PROBE_TAGS", "PROBE_CLASS",
        "MEASUREMENTS", "ACCESSIBLE", "INCONCLUSIVE", "NO_PROBE", "API_ERROR", "RATE_LIMITED",
    ])
    write_tsv(output_dir / "reachability_by_prefix.tsv", prefix_report, [
        "PREFIX", "FAMILY", "ADDRESS_COUNT", "STATUS", "MATCHED_ENDPOINTS",
        "ACCESSIBLE_MEASUREMENTS", "INCONCLUSIVE_MEASUREMENTS", "TARGET_IDS", "POLICY",
    ])
    write_tsv(output_dir / "reachability_candidates.tsv", candidates, [
        "source", "observed_at", "country_requested", "probe_country", "asn_requested",
        "probe_asn", "probe_network", "target_id", "target_domain", "target_ip",
        "ip_family", "port", "result", "error", "measurement_id", "matched_ru_prefix",
    ])
    status["results"] = {
        "globalping_measurements": len(globalping_rows),
        "globalping_accessible": sum(row.get("result") == "ACCESSIBLE" for row in globalping_rows),
        "globalping_inconclusive": sum(row.get("result") == "INCONCLUSIVE" for row in globalping_rows),
        "ooni_observations": len(ooni_rows),
        "ooni_anomaly_review": sum("ANOMALY_REVIEW" in str(row.get("result", "")) for row in ooni_rows),
        "ripe_atlas_records": len(atlas_rows),
        "ru_prefixes_with_accessible_endpoint": sum(row["STATUS"] == "ENDPOINT_ACCESSIBLE_OBSERVED" for row in prefix_report),
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
