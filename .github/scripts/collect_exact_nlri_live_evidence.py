#!/usr/bin/env python3
"""Capture review-only exact-NLRI and RPKI observations from RouteViews and RIPE RIS.

API/network failures are recorded per request and never converted into route absence.
This collector does not change analyst classifications, DIRECT policy or production data.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PREFIXES = (
    "93.181.240.0/20",
    "93.181.248.0/21",
    "94.131.190.0/23",
    "94.131.190.0/24",
    "94.131.191.0/24",
)
USER_AGENT = "Geoip-ru-server-exact-nlri-audit/1.0"
MAX_BODY_BYTES = 4 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_plan() -> list[dict[str, str]]:
    plan: list[dict[str, str]] = []
    for prefix in PREFIXES:
        route_path = urllib.parse.quote(prefix, safe="/:.")
        query = urllib.parse.urlencode({"prefix": prefix})
        ripe_resource = urllib.parse.urlencode({"resource": prefix})
        ripe_lg = urllib.parse.urlencode({"resource": prefix, "look_back_limit": "86400"})
        plan.extend([
            {
                "prefix": prefix,
                "source": "routeviews_exact_rib",
                "url": f"https://api.routeviews.org/prefix/{route_path}?strict-match=yes",
            },
            {
                "prefix": prefix,
                "source": "routeviews_timestamped_rpki",
                "url": f"https://api.routeviews.org/rpki?{query}",
            },
            {
                "prefix": prefix,
                "source": "ripestat_routing_status",
                "url": f"https://stat.ripe.net/data/routing-status/data.json?{ripe_resource}",
            },
            {
                "prefix": prefix,
                "source": "ripestat_looking_glass_24h",
                "url": f"https://stat.ripe.net/data/looking-glass/data.json?{ripe_lg}",
            },
        ])
    return plan


def parse_json_body(raw: bytes) -> tuple[Any | None, str | None]:
    try:
        return json.loads(raw.decode("utf-8")), None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def fetch_one(item: dict[str, str], timeout: float) -> dict[str, Any]:
    started = utc_now()
    before = time.monotonic()
    request = urllib.request.Request(
        item["url"],
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    status: int | None = None
    raw = b""
    transport_status = "NETWORK_ERROR"
    error: str | None = None

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            raw = response.read(MAX_BODY_BYTES + 1)
            transport_status = "HTTP_OK"
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            raw = exc.read(MAX_BODY_BYTES + 1)
        except OSError:
            raw = b""
        transport_status = "HTTP_ERROR"
        error = f"HTTPError: {exc.code} {exc.reason}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # preserve unexpected transport/runtime faults as data
        error = f"{type(exc).__name__}: {exc}"

    finished = utc_now()
    elapsed_ms = round((time.monotonic() - before) * 1000, 1)
    raw_sha256 = hashlib.sha256(raw).hexdigest() if raw else None
    oversized = len(raw) > MAX_BODY_BYTES
    payload: Any | None = None
    parse_error: str | None = None
    body_text: str | None = None

    if oversized:
        error = (error + "; " if error else "") + f"response exceeds {MAX_BODY_BYTES} byte capture limit"
        transport_status = "BODY_TOO_LARGE"
    elif raw:
        payload, parse_error = parse_json_body(raw)
        if payload is None:
            body_text = raw.decode("utf-8", errors="replace")
            if transport_status == "HTTP_OK":
                transport_status = "HTTP_OK_NON_JSON"
            error = (error + "; " if error else "") + f"JSON parse: {parse_error}"

    return {
        "prefix": item["prefix"],
        "source": item["source"],
        "url": item["url"],
        "request_started_utc": started,
        "response_received_utc": finished,
        "elapsed_ms": elapsed_ms,
        "timeout_seconds": timeout,
        "http_status": status,
        "transport_status": transport_status,
        "body_bytes": len(raw),
        "body_sha256": raw_sha256,
        "response_json": payload,
        "response_text": body_text,
        "error": error,
    }


def summarize(record: dict[str, Any]) -> dict[str, Any]:
    """Extract observation metadata only; make no route-policy decisions."""
    payload = record.get("response_json")
    result: dict[str, Any] = {
        "prefix": record["prefix"],
        "source": record["source"],
        "transport_status": record["transport_status"],
        "http_status": record.get("http_status"),
        "response_received_utc": record["response_received_utc"],
        "error": record.get("error"),
    }
    # Never render empty route counts for transport/HTTP/JSON errors: no usable
    # routing response is not evidence that the prefix is absent from BGP.
    if record.get("transport_status") != "HTTP_OK" or payload is None:
        return result
    if record["source"] == "routeviews_exact_rib":
        if not isinstance(payload, list):
            result["response_shape_error"] = "RouteViews exact-prefix response is not a JSON array"
            return result
        entries = payload
        exact = [x for x in entries if isinstance(x, dict) and x.get("prefix") == record["prefix"]]
        origin_rpki = {
            str(x.get("origin_asn")): x.get("rpki_state")
            for x in exact if x.get("origin_asn") is not None
        }
        peer_rows = [
            peer for x in exact for peer in x.get("reporting_peers", [])
            if isinstance(peer, dict)
        ]
        result.update({
            "exact_entries_returned": len(exact),
            "origins": sorted(origin_rpki),
            "origin_rpki_states": origin_rpki,
            "rpki_states": sorted({str(state) for state in origin_rpki.values() if state is not None}),
            "reporting_peer_count": len(peer_rows),
            "collectors": sorted({str(peer.get("collector")) for peer in peer_rows if peer.get("collector")}),
            "latest_peer_timestamp": max(
                (str(peer.get("timestamp")) for peer in peer_rows if peer.get("timestamp")),
                default=None,
            ),
        })
    elif record["source"] == "routeviews_timestamped_rpki":
        if not isinstance(payload, dict):
            result["response_shape_error"] = "RouteViews RPKI response is not a JSON object"
            return result
        prefix_key_present = record["prefix"] in payload
        item = payload.get(record["prefix"]) if prefix_key_present else None
        asn_rows = item.get("asn", []) if isinstance(item, dict) else []
        states = {}
        for row in asn_rows:
            if isinstance(row, dict):
                states.update({str(k): v for k, v in row.items()})
        result.update({
            "prefix_key_present": prefix_key_present,
            "prefix_entry_is_null": prefix_key_present and item is None,
            "snapshot_timestamp": item.get("timestamp") if isinstance(item, dict) else None,
            "origin_states": states,
        })
    elif record["source"] == "ripestat_routing_status":
        api_status = payload.get("status") if isinstance(payload, dict) else None
        data = payload.get("data") if isinstance(payload, dict) else None
        if api_status != "ok" or not isinstance(data, dict) or not isinstance(data.get("origins"), list):
            result.update({
                "api_status": api_status,
                "api_messages": payload.get("messages", []) if isinstance(payload, dict) else [],
                "response_shape_error": "RIPEstat routing-status response is not a successful origins payload",
            })
            return result
        origins = data["origins"]
        result.update({
            "api_status": api_status,
            "query_time": data.get("query_time"),
            "exact_origins": [
                {
                    "origin": row.get("origin"),
                    "route_objects": row.get("route_objects", []),
                }
                for row in origins if isinstance(row, dict)
            ],
            "less_specific_count": len(data.get("less_specifics", [])) if isinstance(data, dict) else None,
            "more_specific_count": len(data.get("more_specifics", [])) if isinstance(data, dict) else None,
        })
    elif record["source"] == "ripestat_looking_glass_24h":
        api_status = payload.get("status") if isinstance(payload, dict) else None
        data = payload.get("data") if isinstance(payload, dict) else None
        rrcs = data.get("rrcs") if isinstance(data, dict) else None
        if api_status != "ok" or not isinstance(data, dict) or not isinstance(rrcs, (list, dict)):
            result.update({
                "api_status": api_status,
                "api_messages": payload.get("messages", []) if isinstance(payload, dict) else [],
                "response_shape_error": "RIPEstat Looking Glass response is not a successful RRC payload",
            })
            return result
        peers = []
        rrc_entries = []
        if isinstance(rrcs, list):
            rrc_entries = [
                (str(rrc.get("rrc", index)), rrc)
                for index, rrc in enumerate(rrcs)
                if isinstance(rrc, dict)
            ]
        elif isinstance(rrcs, dict):
            rrc_entries = [
                (str(rrc), value)
                for rrc, value in rrcs.items()
                if isinstance(value, dict)
            ]
        for rrc, rrc_data in rrc_entries:
            peer_rows = rrc_data.get("peers", rrc_data.get("entries", []))
            for entry in peer_rows if isinstance(peer_rows, list) else []:
                if isinstance(entry, dict):
                    peers.append({
                        "rrc": rrc,
                        "origin": entry.get("asn_origin"),
                        "prefix": entry.get("prefix"),
                        "peer": entry.get("peer"),
                        "as_path": entry.get("as_path"),
                        "last_updated": entry.get("last_updated"),
                        "latest_time": entry.get("latest_time"),
                    })
        result.update({
            "api_status": api_status,
            "query_time": data.get("query_time"),
            "latest_time": data.get("latest_time") if isinstance(data, dict) else None,
            "rrc_count": len(rrc_entries),
            "peer_observation_count": len(peers),
            "origins": sorted({str(x["origin"]) for x in peers if x.get("origin") is not None}),
            "peer_observations": peers,
        })
    return result


def collect(output: Path, timeout: float = 12.0, routeviews_interval: float = 1.1) -> dict[str, Any]:
    plan = build_plan()
    rv_items = [x for x in plan if x["source"].startswith("routeviews_")]
    ripe_items = [x for x in plan if x["source"].startswith("ripestat_")]
    results: list[dict[str, Any]] = []

    # RouteViews documents a 1 request/second unauthenticated guest limit.
    for index, item in enumerate(rv_items):
        if index:
            time.sleep(routeviews_interval)
        results.append(fetch_one(item, timeout))

    # RIPEstat allows up to 8 concurrent requests from one IP.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch_one, item, timeout) for item in ripe_items]
        results.extend(f.result() for f in futures)

    results.sort(key=lambda x: (x["prefix"], x["source"]))
    document = {
        "schema_version": 1,
        "purpose": "review-only exact-NLRI RIB and timestamped RPKI evidence capture",
        "collected_at_utc": utc_now(),
        "prefixes": list(PREFIXES),
        "policy": {
            "classifications_changed": False,
            "status": "REVIEW",
            "api_errors_mean_route_absence": False,
            "routeviews_guest_rate_limit_seconds": routeviews_interval,
            "ripe_looking_glass_look_back_limit_seconds": 86400,
        },
        "request_count": len(results),
        "transport_status_counts": {},
        "results": results,
        "summary": [summarize(row) for row in results],
    }
    counts: dict[str, int] = {}
    for row in results:
        key = row["transport_status"]
        counts[key] = counts.get(key, 0) + 1
    document["transport_status_counts"] = counts
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Exact-NLRI live capture: {len(results)} requests; transport statuses={counts}")
    print("All route/RPKI results are evidence only; no REVIEW classification is changed.")
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--routeviews-interval", type=float, default=1.1)
    args = parser.parse_args()
    if args.timeout <= 0 or args.routeviews_interval < 1.0:
        parser.error("timeout must be positive and RouteViews guest interval must be >= 1.0 seconds")
    try:
        document = collect(args.output, args.timeout, args.routeviews_interval)
    except OSError as exc:
        print(f"Unable to write exact-NLRI capture: {exc}")
        return 1
    return 0 if document["request_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
