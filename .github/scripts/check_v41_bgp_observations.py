#!/usr/bin/env python3
"""Advisory RIPE RIS versus ipverse comparison; never changes DIRECT routes."""
import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import re
import tarfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from build_v41_overlay import intervals, subtract, networks_from_intervals, interval_size

MAX_JSON_BYTES = 10 * 1024 * 1024


def parse_timestamp(value, key):
    if not isinstance(value, str):
        raise ValueError(f"RIPEstat missing {key}")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def window_status(metadata, start, end):
    """Explicitly label a shortened response rather than implying a full 24h."""
    actual_start = parse_timestamp(metadata["query_starttime"], "query_starttime")
    actual_end = parse_timestamp(metadata["query_endtime"], "query_endtime")
    return "partial-window" if actual_start > start + timedelta(hours=1) or actual_end < end - timedelta(hours=1) else "ok"


def read_ipverse(archive_path, selected):
    result = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            match = re.search(r"(?:^|/)as/([0-9]+)/aggregated\.json$", member.name)
            if not match or int(match[1]) not in selected:
                continue
            asn = int(match[1])
            if asn in result or not member.isfile() or not 0 < member.size <= MAX_JSON_BYTES:
                raise ValueError(f"invalid or duplicate archive member for AS{asn}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"unreadable archive member for AS{asn}")
            data = json.load(stream)
            if data.get("asn") != asn or not isinstance(data.get("prefixes"), dict):
                raise ValueError(f"invalid ipverse data for AS{asn}")
            result[asn] = parse_families(data["prefixes"])
    return result


def parse_families(data):
    result = {4: set(), 6: set()}
    for family, key in ((4, "ipv4"), (6, "ipv6")):
        # A missing family is malformed input, not an observed empty table.
        rows = data.get(key)
        if not isinstance(rows, list):
            raise ValueError(f"invalid ipverse {key}")
        for item in rows:
            net = ipaddress.ip_network(item, strict=True)
            if net.version != family or net.prefixlen == 0:
                raise ValueError(f"invalid ipverse prefix {item}")
            result[family].add(net)
    return result


def get_ris(asn, start, end):
    params = urlencode({"resource": f"AS{asn}", "starttime": start.isoformat(),
                        "endtime": end.isoformat(), "min_peers_seeing": 1})
    request = Request("https://stat.ripe.net/data/announced-prefixes/data.json?" + params,
                      headers={"User-Agent": "geoip-v41-bgp-review/1"})
    with urlopen(request, timeout=15) as response:
        payload = response.read(MAX_JSON_BYTES + 1)
    if len(payload) > MAX_JSON_BYTES:
        raise ValueError("RIPEstat response exceeds size limit")
    document = json.loads(payload)
    if document.get("status") != "ok" or not isinstance(document.get("data", {}).get("prefixes"), list):
        raise ValueError("RIPEstat error or unexpected response schema")
    data = document["data"]
    if str(data.get("resource", "")).upper().removeprefix("AS") != str(asn):
        raise ValueError("RIPEstat response has the wrong ASN")
    query_start, query_end, latest = (parse_timestamp(data.get(key), key) for key in ("query_starttime", "query_endtime", "latest_time"))
    if (abs(query_start - start) > timedelta(hours=1) or query_start > query_end or query_end <= start
            or query_end > end + timedelta(hours=1)
            or latest < end - timedelta(hours=48)
            or latest > datetime.now(timezone.utc) + timedelta(hours=1)):
        raise ValueError("RIPEstat response window is stale or outside requested interval")
    families = {4: set(), 6: set()}
    for row in data["prefixes"]:
        net = ipaddress.ip_network(row["prefix"], strict=True)
        if net.prefixlen == 0 or not isinstance(row.get("timelines"), list) or not row["timelines"]:
            raise ValueError("invalid RIPEstat prefix or missing timeline")
        for timeline in row["timelines"]:
            if not isinstance(timeline, dict):
                raise ValueError("invalid RIPEstat timeline")
            first = parse_timestamp(timeline.get("starttime"), "timeline starttime")
            last = parse_timestamp(timeline.get("endtime"), "timeline endtime")
            if first > last or last < query_start or first > query_end:
                raise ValueError("RIPEstat timeline outside response window")
        families[net.version].add(net)
    return families, {key: data.get(key) for key in ("query_starttime", "query_endtime", "latest_time")}


def compare(ipverse, ris):
    output = {}
    for family in (4, 6):
        a, b = intervals(ipverse[family], family), intervals(ris[family], family)
        ris_only, ipverse_only = subtract(b, a), subtract(a, b)
        output[f"ipv{family}"] = {
            "ipverse_addresses": str(interval_size(a)), "ris_addresses": str(interval_size(b)),
            "ris_only_addresses": str(interval_size(ris_only)), "ipverse_only_addresses": str(interval_size(ipverse_only)),
            "ris_only_prefixes": [str(n) for n in sorted(networks_from_intervals(ris_only, family), key=lambda x: (int(x.network_address), x.prefixlen))],
            "ipverse_only_prefixes": [str(n) for n in sorted(networks_from_intervals(ipverse_only, family), key=lambda x: (int(x.network_address), x.prefixlen))],
        }
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--asns", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    if len(set(args.asns)) != len(args.asns) or len(args.asns) > 20 or any(not 0 < n <= 4294967295 for n in args.asns):
        parser.error("ASNs must be unique, valid and at most 20")
    observed = read_ipverse(args.archive, set(args.asns))
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(hours=24)
    results = {}
    for asn in args.asns:
        key = f"AS{asn}"
        if asn not in observed:
            results[key] = {"status": "unavailable", "reason": "ASN absent from ipverse snapshot"}
            continue
        try:
            ris, metadata = get_ris(asn, start, end)
            results[key] = {"status": window_status(metadata, start, end), "ris_window": metadata, **compare(observed[asn], ris)}
        except Exception as exc:  # One failed advisory source must be visible and cannot modify routing.
            results[key] = {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"}
    document = {"generated_at": end.isoformat(), "query_start": start.isoformat(), "query_end": end.isoformat(),
                "min_peers_seeing": 1, "warning": "Different observation windows; discrepancies require review and are not route changes.",
                "asns": results}
    args.output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["## BGP cross-check: advisory", "", "RIPE RIS requested 24h, min_peers_seeing=1; actual data can lag (see JSON metadata). ipverse uses a different window. No automatic routing changes.", "",
             "| ASN | Status | IPv4 RIS-only / ipverse-only addresses | IPv6 RIS-only / ipverse-only addresses |", "|---|---|---:|---:|"]
    for asn, row in results.items():
        if row["status"] in {"ok", "partial-window"}:
            values = [f"{row[f'ipv{v}']['ris_only_addresses']} / {row[f'ipv{v}']['ipverse_only_addresses']}" for v in (4, 6)]
            lines.append(f"| {asn} | {row['status']} | {values[0]} | {values[1]} |")
        else:
            lines.append(f"| {asn} | unavailable | — | — |")
    text = "\n".join(lines) + "\n"
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as stream:
            stream.write(text)
    print(text)


if __name__ == "__main__":
    main()
