#!/usr/bin/env python3
"""Report IP and domain-rule coverage from retained DNS and GeoSite observations."""
import argparse
import csv
from datetime import date, datetime
import gzip
import hashlib
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit

from validate_v41_publication_bounds import read as read_dat

MAX_EVIDENCE = 8 * 1024 * 1024


def read_cases(path):
    cases = {}
    with path.open(encoding="utf-8", newline="") as stream:
        table = csv.DictReader((line for line in stream if not line.startswith("#")), delimiter="\t")
        if table.fieldnames != ["DOMAIN", "SERVICE", "COHORT", "SOURCE_DATE", "EVIDENCE"]:
            raise ValueError("invalid service case header")
        for row in table:
            if None in row or not all(row.values()):
                raise ValueError("invalid service case")
            host = row["DOMAIN"]
            url = urlsplit(row["EVIDENCE"])
            if (host != host.rstrip(".").lower() or host in cases or url.scheme != "https"
                    or not url.hostname or url.username or url.password):
                raise ValueError(f"invalid or duplicate service case: {host}")
            date.fromisoformat(row["SOURCE_DATE"])
            cases[host] = {k.lower(): v for k, v in row.items()}
    return cases


def route(profile, categories, in_direct):
    if profile is None or categories is None:
        return None
    for rule in profile["rules"]:
        if rule["match"] in categories or rule["match"] == "GEOIP_RU" and in_direct is True:
            return rule["outbound"]
        if rule["match"] == "GEOIP_RU" and in_direct is None:
            return None  # No address evidence, so lower rules cannot be declared first.
    return profile["default"]


def family_report(records, direct, profile, categories, version):
    answer_types = {4: 1, 6: 28}
    addresses, cnames = set(), set()
    observations = []
    for record in records:
        timestamp = datetime.fromisoformat(record["time_utc"])
        if timestamp.utcoffset() is None:
            raise ValueError("unqualified DNS observation time")
        positive = record.get("status") == 0
        addrs, aliases = set(), set()
        if positive:
            for answer in record["answers"]:
                if answer["type"] == answer_types[version]:
                    ip = ipaddress.ip_address(answer["data"])
                    if ip.version != version:
                        raise ValueError("DNS record IP family mismatch")
                    addrs.add(ip)
                elif answer["type"] == 5:
                    aliases.add(answer["data"].rstrip(".").lower())
        addresses.update(addrs)
        cnames.update(aliases)
        observations.append({
            **{k: record.get(k) for k in ("resolver", "time_utc", "status", "response_sha256", "error")},
            "addresses": list(map(str, sorted(addrs))), "cnames": sorted(aliases),
        })
    matched = {}
    for ip in sorted(addresses):
        value = int(ip)
        covered = any(lo <= value <= hi for lo, hi in direct)
        matched[str(ip)] = {"geoip_direct": covered, "profile_simulation": route(profile, categories, covered)}
    covered_count = sum(addr["geoip_direct"] for addr in matched.values())
    status = ("NO_DNS_OBSERVATION" if not observations else "NO_ADDRESS_OBSERVED") if not addresses else (
        "ALL_IN_DIRECT" if covered_count == len(matched) else "PARTIAL_DIRECT" if covered_count else "NONE_IN_DIRECT"
    )
    return {
        "geoip": status, "observations": observations, "addresses": matched, "cnames": sorted(cnames),
        "profile_simulation_without_address": None if matched else route(profile, categories, None),
    }


def compare(cases, dns, direct, profile=None):
    domains = {}
    for item in dns["domains"]:
        if item["host"] in domains:
            raise ValueError("duplicate retained GeoSite domain")
        domains[item["host"]] = item["geosite"]
    rows = []
    for host, case in cases.items():
        categories = domains.get(host)
        rows.append({
            **case, "geosite_observed_matches": categories, "actual_client_route": "UNKNOWN",
            "families": {f"ipv{v}": family_report(
                [r for r in dns["dns"] if r["host"] == host and r["qtype"] == qtype],
                direct[v], profile, categories, v)
                for v, qtype in ((4, "A"), (6, "AAAA"))},
        })
    return rows


def evidence_binding(evidence, candidate_sha256, *, replay_on_candidate=False):
    reference = evidence["release_geoip_sha256"]
    if reference == candidate_sha256:
        return "SAME_DAT_AS_OBSERVATION"
    if replay_on_candidate:
        return "FIXED_DNS_REPLAY_ON_DIFFERENT_DAT"
    raise ValueError("DNS and GeoSite evidence was collected against a different GeoIP DAT")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for param in ("cases", "evidence", "dat", "output"):
        parser.add_argument(f"--{param}", required=True, type=Path)
    parser.add_argument("--evidence-sha256", required=True)
    parser.add_argument("--replay-on-candidate", action="store_true", help="reuse fixed historical observations; never claim current DNS")
    parser.add_argument("--profile", type=Path, help="optional JSON projection of first-match client rules")
    args = parser.parse_args()
    try:
        with args.evidence.open("rb") as stream:
            packed = stream.read(MAX_EVIDENCE + 1)
        if len(packed) > MAX_EVIDENCE or hashlib.sha256(packed).hexdigest() != args.evidence_sha256:
            raise ValueError("retained evidence SHA-256 or size mismatch")
        with gzip.open(args.evidence, "rb") as stream:
            raw = stream.read(MAX_EVIDENCE + 1)
        if len(raw) > MAX_EVIDENCE:
            raise ValueError("expanded evidence exceeds limit")
        evidence = json.loads(raw)
        datasets, digest = read_dat(args.dat)
        binding = evidence_binding(evidence, digest, replay_on_candidate=args.replay_on_candidate)
        reviewed = evidence["service_review"]
        profile = profile_sha = None
        if args.profile is not None:
            with args.profile.open("rb") as stream:
                profile_data = stream.read(MAX_EVIDENCE + 1)
            if len(profile_data) > MAX_EVIDENCE:
                raise ValueError("oversized profile")
            profile = json.loads(profile_data)
            if (profile.get("schema") != 1 or profile.get("geosite_commit") != reviewed["geosite_tag_commit"]
                    or set(profile) != {"schema", "geosite_commit", "rules", "default"}
                    or not isinstance(profile["rules"], list)
                    or any(not isinstance(r, dict) or set(r) != {"match", "outbound"}
                           or r["match"] not in {"GEOIP_RU", "RU", "BLOCK", "GOOGLE-PLAY", "GOOGLE-DEEPMIND", "YOUTUBE"}
                           or r["outbound"] not in {"DIRECT", "BLOCK", "PROXY"} for r in profile["rules"])
                    or profile["default"] not in {"DIRECT", "BLOCK", "PROXY"}):
                raise ValueError("invalid or unbound profile projection")
            profile_sha = hashlib.sha256(profile_data).hexdigest()
        rows = compare(read_cases(args.cases), reviewed, datasets["RU"], profile)
        report = {
            "schema": 1, "mode": "REPORT_ONLY", "dat_sha256": digest,
            "observation_dat_sha256": evidence["release_geoip_sha256"], "dns_replay_status": binding,
            "cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(), "evidence_sha256": args.evidence_sha256,
            "geosite_commit": reviewed["geosite_tag_commit"], "geosite_sha256": reviewed["sources"],
            "resolver_sources": reviewed["resolver_urls"], "dns_scope": reviewed["dns_scope"], "client_profile_sha256": profile_sha,
            "rows": rows,
        }
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True)
            output.write("\n")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, EOFError) as exc:
        parser.exit(1, f"service coverage report unavailable: {exc}\n")


if __name__ == "__main__":
    main()
