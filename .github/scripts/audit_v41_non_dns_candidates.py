#!/usr/bin/env python3
"""Classify unconfirmed, non-DNS v41 address gaps. Read-only and never a build input."""

import argparse
import csv
import ipaddress
import json
import tarfile
from bisect import bisect_left
from collections import Counter, defaultdict
from pathlib import Path

from audit_v41_additional_geoip import (
    SOURCES, GROUPS, additional_eligibility, category_allowed, read_cidrs, sha,
    unconfirmed_additional_space,
)
from build_v41_overlay import (
    intersect, interval_size, intervals, networks_from_intervals, normalize_interval_union,
    parse_geoip_dat, parse_regional_admission_exclusions, parse_rir_tsv, subtract,
)
from validate_v41_telegram import PINNED_FEED, read_telegram_feed


def reconstruct(artifact, sources, archive, admission, telegram, version=4):
    provenance = artifact / "geoip_RU_input_provenance.tsv"
    if provenance.with_name(provenance.name + ".sha256sum").read_text().split()[0] != sha(provenance):
        raise ValueError("Locked provenance checksum mismatch")
    with provenance.open(encoding="utf-8", newline="") as f:
        index = {r["LOCAL_FILE"]: r for r in csv.DictReader(f, delimiter="\t")}
    locked = {}
    for path in [archive, *(sources / name for name in SOURCES.values())]:
        rec = index[path.name]
        if path.stat().st_size != int(rec["BYTES"]) or sha(path) != rec["SHA256"]:
            raise ValueError(f"Production source mismatch: {path}")
        locked[path.name] = rec["SHA256"]
    manifest = json.loads((artifact / "geoip_RU_v41_manifest.json").read_text())
    names = {
        "base_v37_geoip": "geoip_RU_v37_base.dat",
        "v37_blocked_base": "geoip_RU_blocked_ip_exclusions.txt",
        "blocked_exact_and_legacy": "geoip_RU_blocked_ip_exact_and_legacy_hard.txt",
        "blocked_resolver_only": "geoip_RU_blocked_ipresolve_resolver_only.txt",
        "regional_rir_inventory": "geoip_RU_BY_KZ_rir_registered_prefixes.tsv",
        "regional_origin_prefixes": "geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt",
        "corporate_company_asn_origin_prefixes": "geoip_RU_company_asn_bgp_prefixes.txt",
    }
    for key, name in names.items():
        if sha(artifact / name) != manifest["input_sha256"][key]:
            raise ValueError(f"Production input mismatch: {name}")
    if sha(admission) != manifest["input_sha256"]["regional_admission_exclusions"]:
        raise ValueError("Production regional admission mismatch")
    dat = artifact / "geoip_RU.dat"
    eff = artifact / "geoip_RU_v41_blocked_ip_exclusions.txt"
    if (sha(dat) != manifest["output_sha256"]
            or dat.with_name(dat.name + ".sha256sum").read_text().split()[0] != sha(dat)
            or eff.with_name(eff.name + ".sha256sum").read_text().split()[0] != sha(eff)):
        raise ValueError("Production output mismatch")
    feeds = {
        name: intervals({net for tag, nets in parse_geoip_dat(sources / filename).items()
                         if category_allowed(name, tag) for net in nets}, version)
        for name, filename in SOURCES.items()
    }
    datsets = parse_geoip_dat(dat)
    masks = {
        "asn": intervals(read_cidrs(artifact / "geoip_RU_BY_KZ_asn_bgp_prefixes.txt"), version),
        "rir_ru": intervals(read_cidrs(artifact / "geoip_RU_rir_registered_prefixes.txt"), version),
        "private": intervals(datsets["PRIVATE"], version),
    }
    all_additional, two, eligible = additional_eligibility(feeds, masks)
    one = unconfirmed_additional_space(all_additional, eligible, feeds, masks)
    if intersect(one, two) or intersect(one, masks["rir_ru"]):
        raise ValueError("Unexpected positive admission evidence in one-group cohort")
    approved = intervals(read_cidrs(artifact / names["v37_blocked_base"]), version)
    with (artifact / "geoip_RU_v37_additional_provenance.tsv").open(encoding="utf-8", newline="") as f:
        accepted = intervals({ipaddress.ip_network(r["PREFIX"]) for r in csv.DictReader(f, delimiter="\t")}, version)
    if subtract(eligible, approved) != accepted:
        raise ValueError("Published v37 coverage mismatch")
    base_sets = parse_geoip_dat(artifact / names["base_v37_geoip"])
    if set(datsets) != {"RU", "PRIVATE"} or set(base_sets) != {"RU", "PRIVATE"} or any(
        intervals(datsets["PRIVATE"], v) != intervals(base_sets["PRIVATE"], v) for v in (4, 6)
    ):
        raise ValueError("Unexpected categories or PRIVATE drift")
    if subtract(accepted, intervals(base_sets["RU"], version)):
        raise ValueError("Published v37 evidence is not a subset of the base")
    base = intervals(base_sets["RU"], version)
    hard = intervals(read_cidrs(artifact / names["blocked_exact_and_legacy"]) | read_telegram_feed(telegram), version)
    resolver = intervals(read_cidrs(artifact / names["blocked_resolver_only"]), version)
    final = intervals(datsets["RU"], version)
    removed = intervals(set(parse_regional_admission_exclusions(admission)), version)
    result = subtract(one, normalize_interval_union(final, base, approved, hard, resolver,
                                                    intervals(read_cidrs(eff), version), removed, masks["private"]))
    registered, _ = parse_rir_tsv(artifact / names["regional_rir_inventory"])
    corroboration = {
        "v41 regional registered resources": intervals(set().union(*registered.values()), version),
        "v41 regional BGP layer": intervals(read_cidrs(artifact / names["regional_origin_prefixes"]), version),
        "v41 corporate BGP layer": intervals(read_cidrs(artifact / names["corporate_company_asn_origin_prefixes"]), version),
    }
    for label, known in corroboration.items():
        if intersect(result, known):
            raise ValueError(f"Unexpected {label} overlap in one-group discovery")
    return result, feeds, locked, manifest["output_sha256"]


def match_archive(archive, candidates, version=4):
    """Group observed CIDRs by exact key and preserve MOAS at longest match."""
    last_addresses = [end for _, end in candidates]
    origins = defaultdict(set)
    metadata = {}
    with tarfile.open(archive, "r|gz") as f:
        for member in f:
            if not member.isfile() or not member.name.endswith("/aggregated.json"):
                continue
            data = json.load(f.extractfile(member))
            asn = int(data["asn"])
            net_type = ipaddress.IPv4Network if version == 4 else ipaddress.IPv6Network
            for value in (data.get("prefixes") or {}).get(f"ipv{version}", []):
                net = net_type(value, strict=False)
                if net.prefixlen == 0:
                    continue
                start, end = int(net.network_address), int(net.broadcast_address)
                i = bisect_left(last_addresses, start)
                if i < len(candidates) and candidates[i][0] <= end:
                    origins[net].add(asn)
                    meta = data.get("metadata") or {}
                    metadata[asn] = {k: meta.get(k) for k in ("handle", "description", "countryCode")}
    return origins, metadata


def partition(candidates, origins, version=4):
    uncovered = candidates
    for net, asns in sorted(origins.items(), key=lambda item: (-item[0].prefixlen, int(item[0].network_address))):
        win = intersect(uncovered, intervals({net}, version))
        if win:
            yield net, sorted(asns), win
            uncovered = subtract(uncovered, win)
        if not uncovered:
            break
    if uncovered:
        yield None, [], uncovered


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--admission", type=Path, required=True)
    p.add_argument("--telegram", type=Path, default=PINNED_FEED)
    p.add_argument("--version", type=int, choices=(4, 6), default=4)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    version = args.version
    candidates, feeds, locked, dat_sha = reconstruct(args.artifact, args.source_dir, args.archive, args.admission, args.telegram, version)
    origins, metadata = match_archive(args.archive, candidates, version)
    rows, status, stats = [], Counter(), Counter()
    source_groups = {"+".join(group): normalize_interval_union(*(feeds[s] for s in group)) for group in GROUPS}
    for net, asns, iv in partition(candidates, origins, version):
        count = interval_size(iv)
        status["not_observed" if not asns else "moas" if len(asns) > 1 else "single_origin"] += count
        if len(asns) == 1:
            stats[asns[0]] += count
        by_group = {name: interval_size(intersect(iv, group)) for name, group in source_groups.items()}
        if sum(by_group.values()) != count:
            raise ValueError("Candidate group counts do not partition the set")
        rows.append({
            "observed_prefix": str(net) if net else None, "origins": asns, "candidate_addresses": count,
            "candidate_cidrs": [str(n) for n in sorted(networks_from_intervals(iv, version))], "source_groups": by_group,
        })
    total = interval_size(candidates)
    if sum(status.values()) != total:
        raise ValueError("BGP partition does not reconcile")
    report = {
        "dat_sha256": dat_sha, "locked_input_sha256": locked, f"ipv{version}": total,
        "cidrs": len(networks_from_intervals(candidates, version)), "coverage_by_observation": dict(status),
        "single_origin_ranking": [{"asn": n, "candidate_addresses": cnt, **metadata[n]}
                                  for n, cnt in sorted(stats.items(), key=lambda x: (-x[1], x[0]))],
        "observed_origin_metadata": metadata, "longest_observed_prefix_rows": rows,
        "note": "Frozen ipverse observation, not a live exact NLRI, assignment, or proof of reachability.",
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("dat_sha256", f"ipv{version}", "cidrs", "coverage_by_observation")}, indent=2))


if __name__ == "__main__":
    main()
