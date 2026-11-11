#!/usr/bin/env python3
"""Capture RIPEstat RPKI validation for exact prefix/origin pairs.

The RIPEstat validator is an independent view of the prefix+ASN validity
decision. API errors and unknown states are preserved and never treated as
proof that a route is absent or safe.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

SOURCES = {
    "routeviews_exact_rib",
    "ripestat_routing_status",
    "ripestat_looking_glass_24h",
}
USER_AGENT = "Geoip-RU-postrelease-audit/1.0"
MIN_START_INTERVAL = 0.25
_last_start = 0.0
_start_lock = threading.Lock()


def _throttle() -> None:
    global _last_start
    with _start_lock:
        now = time.monotonic()
        delay = MIN_START_INTERVAL - (now - _last_start)
        if delay > 0:
            time.sleep(delay)
        _last_start = time.monotonic()


def collect_pairs(capture: dict[str, Any], targets: list[dict[str, str]]) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for item in capture.get("summary", []):
        if item.get("source") not in SOURCES:
            continue
        prefix = item.get("prefix")
        if not prefix:
            continue
        for origin in item.get("exact_origins") or []:
            asn = re.sub(r"^AS", "", str(origin).strip(), flags=re.IGNORECASE)
            if asn.isdigit():
                pairs.add((prefix, asn))
    for row in targets:
        prefix = row.get("PREFIX")
        for origin in re.findall(r"AS?(\d+)", row.get("ARCHIVED_INVALID_ORIGINS", ""), re.IGNORECASE):
            if prefix:
                pairs.add((prefix, origin))
    return sorted(pairs)


def normalize_routeviews_status(value: str) -> str:
    compact = "".join(ch for ch in str(value).strip().casefold() if ch.isalnum())
    if compact == "valid":
        return "valid"
    if compact == "invalid":
        return "invalid"
    if compact in {"notfound", "unknown", "notavailable"}:
        return "unknown"
    return "unusable"


def normalize_ripestat_status(value: str) -> str:
    compact = "".join(ch for ch in str(value).strip().casefold() if ch.isalnum())
    if compact == "valid":
        return "valid"
    if compact in {"invalidasn", "invalidlength", "invalid"}:
        return "invalid"
    if compact == "unknown":
        return "unknown"
    return "unusable"


def compare_status(route_state: str, ripe_state: str) -> str:
    route = normalize_routeviews_status(route_state)
    ripe = normalize_ripestat_status(ripe_state)
    if "unusable" in {route, ripe}:
        return "UNUSABLE_OR_MISSING_STATE"
    if route == "unknown" and ripe == "unknown":
        return "BOTH_UNKNOWN_NO_ROA"
    return "MATCH" if route == ripe else "STATUS_DISAGREEMENT"


def _request_one(pair: tuple[str, str], timeout: float, retries: int) -> dict[str, Any]:
    prefix, asn = pair
    query = urllib.parse.urlencode({
        "resource": asn,
        "prefix": prefix,
        "cache": "ignore",
        "sourceapp": "geoip-ru-postrelease-audit",
    })
    url = f"https://stat.ripe.net/data/rpki-validation/data.json?{query}"
    prior_errors: list[str] = []
    started_all = time.time()
    for attempt in range(1, retries + 2):
        _throttle()
        request_started = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read()
                received = time.time()
                digest = hashlib.sha256(body).hexdigest()
                payload = json.loads(body.decode("utf-8"))
                api_envelope = payload.get("status")
                api_status = "OK" if api_envelope == "ok" and payload.get("data_call_status") == "supported" else "API_ERROR"
                data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
                data_status = data.get("status")
                return {
                    "prefix": prefix,
                    "asn": asn,
                    "source": "ripestat_rpki_validation",
                    "url": url,
                    "request_started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(request_started)),
                    "response_received_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(received)),
                    "elapsed_ms": round((received - request_started) * 1000, 3),
                    "attempt_count": attempt,
                    "http_status": response.status,
                    "transport_status": "HTTP_OK",
                    "api_status": api_status,
                    "data_status": data_status,
                    "description": data.get("description"),
                    "response_bytes": len(body),
                    "response_sha256": digest,
                    "response_json": payload,
                    "prior_attempt_errors": prior_errors,
                    "error": None if api_status == "OK" and data_status else f"RIPEstat response status={api_envelope}, data_call_status={payload.get('data_call_status')}, data.status={data_status}",
                }
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            received = time.time()
            message = f"HTTP {exc.code}: {raw[:500].decode('utf-8', 'replace')}"
            prior_errors.append(message)
            if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt > retries:
                return {
                    "prefix": prefix, "asn": asn, "source": "ripestat_rpki_validation", "url": url,
                    "request_started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(request_started)),
                    "response_received_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(received)),
                    "elapsed_ms": round((received - request_started) * 1000, 3), "attempt_count": attempt,
                    "http_status": exc.code, "transport_status": "HTTP_ERROR", "api_status": "NOT_CHECKED",
                    "data_status": None, "description": None, "response_bytes": len(raw),
                    "response_sha256": hashlib.sha256(raw).hexdigest(), "response_json": None,
                    "prior_attempt_errors": prior_errors[:-1], "error": message,
                }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            received = time.time()
            prior_errors.append(f"{type(exc).__name__}: {exc}")
            if attempt > retries:
                return {
                    "prefix": prefix, "asn": asn, "source": "ripestat_rpki_validation", "url": url,
                    "request_started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(request_started)),
                    "response_received_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(received)),
                    "elapsed_ms": round((received - request_started) * 1000, 3), "attempt_count": attempt,
                    "http_status": None, "transport_status": "TRANSPORT_ERROR", "api_status": "NOT_CHECKED",
                    "data_status": None, "description": None, "response_bytes": 0, "response_sha256": None,
                    "response_json": None, "prior_attempt_errors": prior_errors[:-1], "error": prior_errors[-1],
                }
        time.sleep(min(2 ** (attempt - 1), 8))
    raise RuntimeError(f"unreachable retry state for {prefix} AS{asn}; started {started_all}")


def collect(input_dir: Path, output_dir: Path, timeout: float = 18.0, workers: int = 4, retries: int = 2) -> dict[str, Any]:
    capture = json.loads((input_dir / "exact_nlri_capture.json").read_text(encoding="utf-8"))
    with (input_dir / "v38_postrelease_prefix_review.tsv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    pairs = collect_pairs(capture, rows)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_request_one, pair, timeout, retries) for pair in pairs]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: (item["prefix"], int(item["asn"])))

    raw_path = output_dir / "ripestat_rpki_validation.jsonl"
    with raw_path.open("w", encoding="utf-8", newline="\n") as fh:
        for item in results:
            fh.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")

    validation_by_prefix: dict[str, dict[str, dict[str, Any]]] = {}
    for item in results:
        validation_by_prefix.setdefault(item["prefix"], {})[item["asn"]] = {
            "api_status": item["api_status"],
            "status": item["data_status"],
            "description": item["description"],
            "transport_status": item["transport_status"],
            "response_received_utc": item["response_received_utc"],
            "response_sha256": item["response_sha256"],
            "error": item["error"],
        }

    updated_rows = []
    route_level_conflicts = []
    compare_counts: Counter[str] = Counter()
    data_status_counts: Counter[str] = Counter()
    for row in rows:
        prefix = row["PREFIX"]
        values = validation_by_prefix.get(prefix, {})
        route_states = json.loads(row.get("ROUTEVIEWS_ROUTE_LEVEL_RPKI") or "{}")
        comparisons = {}
        for asn in sorted(set(route_states) & set(values), key=int):
            route_state = route_states[asn]
            ripe_state = values[asn].get("status")
            result = compare_status(route_state, ripe_state or "")
            comparisons[asn] = {
                "routeviews_route_level": route_state,
                "ripestat_rpki_validation": ripe_state,
                "comparison": result,
            }
            compare_counts[result] += 1
            if result == "STATUS_DISAGREEMENT":
                route_level_conflicts.append({"prefix": prefix, "asn": asn, **comparisons[asn]})
        row["RIPESTAT_RPKI_VALIDATION"] = json.dumps(values, sort_keys=True, separators=(",", ":"))
        row["RIPESTAT_RPKI_VALIDATION_ROUTE_LEVEL_COMPARISON"] = json.dumps(comparisons, sort_keys=True, separators=(",", ":"))
        updated_rows.append(row)
        for value in values.values():
            data_status_counts[str(value.get("status") or "NO_DATA")] += 1

    fields = list(updated_rows[0].keys()) if updated_rows else []
    with (output_dir / "v38_postrelease_prefix_review.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(updated_rows)

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    transport_counts = Counter(item["transport_status"] for item in results)
    api_counts = Counter(item["api_status"] for item in results)
    manifest["ripestat_rpki_validation"] = {
        "request_count": len(pairs),
        "completed_record_count": len(results),
        "transport_status_counts": dict(sorted(transport_counts.items())),
        "api_status_counts": dict(sorted(api_counts.items())),
        "data_status_counts": dict(sorted(data_status_counts.items())),
        "route_level_comparison_counts": dict(sorted(compare_counts.items())),
        "route_level_status_disagreements": route_level_conflicts,
        "purpose": "Independent official RIPEstat/Routinator validation for all current exact-origin pairs across RouteViews/RIPEstat plus archived-invalid origin/prefix pairs.",
        "limitations": "unknown is not valid or invalid; API/transport errors are not treated as missing routes; this validation does not promote or exclude any prefix.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_path = output_dir / "ripestat_rpki_validation.tsv"
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        fields = ["PREFIX", "ASN", "API_STATUS", "RPKI_STATUS", "DESCRIPTION", "TRANSPORT_STATUS", "RESPONSE_RECEIVED_UTC", "RESPONSE_SHA256", "ERROR"]
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for item in results:
            writer.writerow({
                "PREFIX": item["prefix"], "ASN": item["asn"], "API_STATUS": item["api_status"],
                "RPKI_STATUS": item["data_status"], "DESCRIPTION": item["description"],
                "TRANSPORT_STATUS": item["transport_status"], "RESPONSE_RECEIVED_UTC": item["response_received_utc"],
                "RESPONSE_SHA256": item["response_sha256"], "ERROR": item["error"],
            })

    report = {
        "pairs": len(pairs),
        "results": len(results),
        "transport_status_counts": dict(sorted(transport_counts.items())),
        "api_status_counts": dict(sorted(api_counts.items())),
        "data_status_counts": dict(sorted(data_status_counts.items())),
        "route_level_comparison_counts": dict(sorted(compare_counts.items())),
        "route_level_status_disagreements": route_level_conflicts,
        "status_rows": sum(1 for row in updated_rows if row["STATUS"] == "REVIEW"),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if len(updated_rows) != 56 or any(row["STATUS"] != "REVIEW" for row in updated_rows):
        raise ValueError("RIPEstat RPKI enrichment modified the review-only status invariant")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=18.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    collect(args.input_dir, args.output_dir, args.timeout, args.workers, args.retries)


if __name__ == "__main__":
    main()
