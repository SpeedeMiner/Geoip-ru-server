#!/usr/bin/env python3
"""Compare observed, selected and final-DIRECT address space for watched origins."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
import ipaddress
import json
from pathlib import Path
import re
import tarfile
from urllib.parse import urlsplit

from build_v41_overlay import intersect, interval_size, intervals, subtract
from validate_v41_publication_bounds import read as read_dat
from v41_asn_observations import classify_prefix
from v41_release_manifest import MANIFEST, describe, verify
from verify_v41_ipverse_archive import ARCHIVE, archive_record, verify_archive

PROVENANCE = "geoip_RU_input_provenance.tsv"
POLICY = "geoip_RU_v41_manifest.json"
SELECTED = "geoip_RU_BY_KZ_asn_bgp_prefixes.txt"
BOUND_ORIGINS = "geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt"
DAT = "geoip_RU.dat"
FILES = (ARCHIVE, PROVENANCE, POLICY, BOUND_ORIGINS, SELECTED, DAT)
AS_RE = r"AS([1-9][0-9]{0,9})"
ORIGIN = re.compile(AS_RE + r"\[([^\[\],]+)\](\[STATIC-DIRECT\])?")
REJECTED = ("invalid", "default", "wrong_family", "invalid_family_schema")


def read_watchlist(path):
    watch = {}
    with path.open(encoding="utf-8", newline="") as stream:
        rows = csv.DictReader((line for line in stream if not line.startswith("#")), delimiter="\t")
        if rows.fieldnames != ["ASN", "GROUP", "ENTITY", "EVIDENCE"]:
            raise ValueError("unexpected priority ASN watchlist header")
        for row in rows:
            match = re.fullmatch(AS_RE, row["ASN"] or "")
            if None in row or not all(row.values()) or not match:
                raise ValueError("invalid priority ASN watchlist row")
            number = int(match[1])
            evidence = urlsplit(row["EVIDENCE"])
            if (number > 0xffffffff or number in watch or evidence.scheme != "https"
                    or not evidence.hostname or evidence.username or evidence.password):
                raise ValueError(f"invalid or duplicate watchlist entry for AS{number}")
            watch[number] = {k.lower(): row[k] for k in ("GROUP", "ENTITY", "EVIDENCE")}
    if not watch:
        raise ValueError("empty priority ASN watchlist")
    return watch


def read_observed(path, watch):
    observed = {}
    member_re = re.compile(r"(?:[^/]+/)?as/([1-9][0-9]{0,9})/aggregated\.json")
    with tarfile.open(path, mode="r|gz") as archive:
        for member in archive:
            match = member_re.fullmatch(member.name)
            if not match or (number := int(match[1])) not in watch:
                continue
            if not member.isfile() or number in observed or not 0 < member.size <= 16 * 1024 * 1024:
                raise ValueError(f"invalid or duplicate watched ASN member: {member.name}")
            with archive.extractfile(member) as stream:
                payload = json.load(stream)
            if not isinstance(payload, dict) or type(payload.get("asn")) is not int or payload["asn"] != number:
                raise ValueError(f"ASN identity mismatch: {member.name}")
            families = observed[number] = {}
            prefixes = payload.get("prefixes")
            for version in (4, 6):
                label = f"ipv{version}"
                counts, nets, problems = Counter(), set(), []
                records = prefixes.get(label, []) if isinstance(prefixes, dict) else None
                if not isinstance(records, list):
                    counts["invalid_family_schema"] += 1
                    problems.append({"type": "invalid_family_schema", "field": f"prefixes.{label}"})
                    records = []
                for index, raw in enumerate(records):
                    outcome, network = classify_prefix(raw, version)
                    counts[outcome] += 1
                    if network is not None:
                        nets.add(network)
                    else:
                        problems.append({"type": outcome, "field": f"prefixes.{label}[{index}]", "value": str(raw)[:160]})
                families[version] = (nets, counts, problems, member.name)
    return observed


def read_selected(path, watch):
    selected = defaultdict(set)
    pins = defaultdict(set)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        prefix, sep, labels = line.partition(" # ")
        if not sep:
            raise ValueError("selected origin row lacks ASN labels")
        network = ipaddress.ip_network(prefix)
        if network.prefixlen == 0:
            raise ValueError("default route in selected origin inventory")
        for label in labels.split(","):
            match = ORIGIN.fullmatch(label)
            if not match:
                raise ValueError(f"invalid origin label: {label}")
            if (number := int(match[1])) in watch:
                key = (number, network.version)
                selected[key].add(network)
                if match[3]:
                    pins[key].add(network)
    return selected, pins


def verified_snapshot(root, watch):
    hashes = {name: describe(root / name)["sha256"] for name in FILES if name != ARCHIVE}
    if (root / MANIFEST).is_file():
        verify(root, root / MANIFEST, (ARCHIVE, PROVENANCE, POLICY, DAT))
        hashes[MANIFEST] = describe(root / MANIFEST)["sha256"]
    policy = json.loads((root / POLICY).read_bytes())
    for field, name in (("output_sha256", DAT), ("input_provenance_sha256", PROVENANCE)):
        if policy[field] != hashes[name]:
            raise ValueError(f"policy hash mismatch: {name}")
    if policy["input_sha256"]["regional_origin_prefixes"] != hashes[BOUND_ORIGINS]:
        raise ValueError("policy hash mismatch: regional origin sidecar")
    with (root / BOUND_ORIGINS).open(encoding="utf-8") as stream:
        bound = [line.strip().partition("=")[2] for line in stream if line.startswith("# selected_origin_input_sha256=")]
    if bound != [hashes[SELECTED]]:
        raise ValueError("regional origin sidecar does not bind the selected origin inventory")
    verify_archive(root / PROVENANCE, root / ARCHIVE)
    _, hashes[ARCHIVE], _ = archive_record(root / PROVENANCE)
    direct, decoded_sha = read_dat(root / DAT)
    if decoded_sha != hashes[DAT]:
        raise ValueError("DAT changed during audit")
    return {
        "hashes": hashes, "observed": read_observed(root / ARCHIVE, watch),
        "selected": read_selected(root / SELECTED, watch), "direct": direct["RU"],
    }


def as_cidrs(ranges, version):
    addr = ipaddress.IPv4Address if version == 4 else ipaddress.IPv6Address
    return [str(net) for lo, hi in ranges for net in ipaddress.summarize_address_range(addr(lo), addr(hi))]


def metric(ranges, version, source_count=None):
    out = {"addresses": str(interval_size(ranges)), "minimal_cidrs": len(as_cidrs(ranges, version))}
    if source_count is not None:
        out["unique_source_prefixes"] = source_count
    return out


def family_snapshot(snapshot, key):
    asn, version = key
    observed_row = snapshot["observed"].get(asn, {}).get(version)
    observed, counts, problems, member = observed_row or (set(), Counter(), [], None)
    chosen = snapshot["selected"][0].get(key, set())
    pins = snapshot["selected"][1].get(key, set())
    raw = {"observed": observed, "selected": chosen, "static_selected_pins": pins}
    ranges = {name: intervals(nets, version) for name, nets in raw.items()}
    ranges["selected_in_direct"] = intersect(ranges["selected"], snapshot["direct"][version])
    ranges["observed_in_direct"] = intersect(ranges["observed"], snapshot["direct"][version])
    ranges["selected_outside_direct"] = subtract(ranges["selected"], snapshot["direct"][version])
    state = ("ASN_NOT_OBSERVED" if not member else "OBSERVED"
             if observed else "NO_VALID_PREFIX_AFTER_REJECTION" if problems else "FAMILY_NOT_OBSERVED")
    return ranges, {
        "observation": state, "source_member": member,
        "parser_counts": None if member is None else {name: counts[name] for name in ("valid", "normalized", *REJECTED)},
        "rejected_records": problems,
        "selected_outside_direct_cidrs": as_cidrs(ranges["selected_outside_direct"], version),
        "layers": {name: metric(parts, version, len(raw[name]) if name in raw else None) for name, parts in ranges.items()},
    }


def evidence_ranges(ranges, version):
    cidrs = as_cidrs(ranges, version)
    return {"addresses": str(interval_size(ranges)), "minimal_cidrs": len(cidrs), "cidrs": cidrs}


def observed_fingerprints(watch, observed):
    """Hash only valid watched routes, preserving ASN and family boundaries."""
    identity = sha256()
    coverage = sha256()
    prefixes_by_pair = {}
    coverage_by_pair = {}
    for asn in sorted(watch):
        for version in (4, 6):
            record = observed.get(asn, {}).get(version)
            prefixes = tuple(sorted(record[0], key=lambda n: (int(n.network_address), n.prefixlen))) if record else ()
            union = tuple(intervals(prefixes, version))
            pair = (asn, version)
            prefixes_by_pair[pair] = prefixes
            coverage_by_pair[pair] = union
            # Canonical integers and explicit delimiters also handle IPv6 without rounding.
            prefix_line = ",".join(f"{int(n.network_address)}/{n.prefixlen}" for n in prefixes)
            coverage_line = ",".join(f"{lo}-{hi}" for lo, hi in union)
            identity.update(f"{asn}:{version}:{prefix_line}\n".encode("ascii"))
            coverage.update(f"{asn}:{version}:{coverage_line}\n".encode("ascii"))
    return {
        "normalized_prefix_sha256": identity.hexdigest(),
        "normalized_address_union_sha256": coverage.hexdigest(),
    }, prefixes_by_pair, coverage_by_pair


def summarize_observed_changes(watch, previous, candidate):
    current, current_prefixes, current_coverage = observed_fingerprints(watch, candidate["observed"])
    base = prefix_pairs = coverage_pairs = None
    if previous is None:
        status = "NO_VERIFIED_BASELINE"
    else:
        base, prior_prefixes, prior_coverage = observed_fingerprints(watch, previous["observed"])
        prefix_pairs = sum(prefixes != prior_prefixes[key] for key, prefixes in current_prefixes.items())
        coverage_pairs = sum(coverage != prior_coverage[key] for key, coverage in current_coverage.items())
        if coverage_pairs:
            status = "WATCHED_ADDRESS_SPACE_CHANGED"
        elif prefix_pairs:
            status = "WATCHED_PREFIX_SHAPE_CHANGED_WITHOUT_ADDRESS_CHANGE"
        elif previous["hashes"][ARCHIVE] != candidate["hashes"][ARCHIVE]:
            status = "DIFFERENT_ARCHIVE_SAME_WATCHED_PREFIXES"
        else:
            status = "IDENTICAL_ARCHIVE"
    return {
        "schema": 1, "status": status, "candidate": current, "previous": base,
        "watchlist_asns": len(watch),
        "changed_prefix_pairs": prefix_pairs, "changed_address_space_pairs": coverage_pairs,
        "scope": "Valid candidate and baseline routes for watched ASN/family pairs only; parser errors and missing observations are tracked separately.",
    }


def summarize_impact(rows):
    baseline_available = any(row["previous_selected_direct_impact"] is not None for row in rows)
    return {
        "baseline_available": baseline_available,
        "asn_family_pairs": len(rows),
        "affected_pairs": {
            "attribution_loss_direct_retained": sum(
                "ASN_ATTRIBUTION_LOSS_DIRECT_RETAINED" in row["review_reasons"] for row in rows),
            "space_lost_from_final_direct": sum(
                "PREVIOUS_ASN_SELECTED_SPACE_LOST_FROM_FINAL_DIRECT" in row["review_reasons"] for row in rows),
        } if baseline_available else None,
        "counts_are_pairs_not_unique_addresses": True,
    }


def compare(watch, previous, candidate):
    rows = []
    for asn, scope in sorted(watch.items()):
        for version in (4, 6):
            current_ranges, current = family_snapshot(candidate, (asn, version))
            before_ranges, before = family_snapshot(previous, (asn, version)) if previous else (None, None)
            reasons = []
            if current["rejected_records"]:
                reasons.append("PARSER_REJECTED_RECORDS")
            if before is None:
                reasons.append("NO_VERIFIED_BASELINE")
            elif before_ranges["observed"] and not current_ranges["observed"]:
                reasons.append("PREVIOUSLY_OBSERVED_FAMILY_LOST")
            impact = None
            if before_ranges is not None:
                reduced = subtract(before_ranges["selected_in_direct"], current_ranges["selected_in_direct"])
                retained = intersect(reduced, candidate["direct"][version])
                missing = subtract(reduced, candidate["direct"][version])
                impact = {
                    "retained_in_final_direct": evidence_ranges(retained, version),
                    "removed_from_final_direct": evidence_ranges(missing, version),
                }
                if reduced:
                    reasons.append("PREVIOUS_SELECTED_DIRECT_SPACE_REDUCED")
                if retained:
                    reasons.append("ASN_ATTRIBUTION_LOSS_DIRECT_RETAINED")
                if missing:
                    reasons.append("PREVIOUS_ASN_SELECTED_SPACE_LOST_FROM_FINAL_DIRECT")
            if not current_ranges["observed"] and not current["rejected_records"]:
                reasons.append("ABSENCE_UNCONFIRMED")
            delta = None if before is None else {
                name: {direction: evidence_ranges(parts, version)
                       for direction, parts in (
                           ("added", subtract(after, before_ranges[name])),
                           ("removed", subtract(before_ranges[name], after)))}
                for name, after in current_ranges.items()
            }
            rows.append({"asn": asn, **scope, "family": version, "candidate": current,
                         "previous": before, "delta": delta, "previous_selected_direct_impact": impact,
                         "review_reasons": reasons})
    return rows


def write_summary(report, stream):
    """Expose actionable coverage drift without presenting absent evidence as zero."""
    impact = report["direct_impact_summary"]
    print("### Priority ASN and IPv6 coverage (advisory)", file=stream)
    print(f"- Watched ASN/family pairs: {impact['asn_family_pairs']}", file=stream)
    if not impact["baseline_available"]:
        print("- Previous release unavailable: coverage changes are unknown.", file=stream)
    else:
        counts = impact["affected_pairs"]
        print(f"- Pinned release: `{report['previous_release']}`", file=stream)
        print(f"- Pairs with attribution loss retained in DIRECT: {counts['attribution_loss_direct_retained']}", file=stream)
        print(f"- Pairs with prior selected space lost from final DIRECT: {counts['space_lost_from_final_direct']}", file=stream)
        print(f"- Watched observation identity: `{report['observed_snapshot_identity']['status']}`", file=stream)
        losses = [r for r in report["rows"] if "PREVIOUS_ASN_SELECTED_SPACE_LOST_FROM_FINAL_DIRECT" in r["review_reasons"]]
        for row in losses[:10]:
            cidrs = row["previous_selected_direct_impact"]["removed_from_final_direct"]["cidrs"]
            print(f"  - AS{row['asn']} IPv{row['family']}: " + ", ".join(f"`{c}`" for c in cidrs[:10]), file=stream)
    unconfirmed = sum("ABSENCE_UNCONFIRMED" in row["review_reasons"] for row in report["rows"])
    rejected = sum("PARSER_REJECTED_RECORDS" in row["review_reasons"] for row in report["rows"])
    print(f"- Unconfirmed absent observations: {unconfirmed}; pairs with rejected records: {rejected}", file=stream)
    print("\nCounts are ASN/family pairs, not unique IP totals. Observations and removals do not prove service reachability or failure; the artifact contains exact CIDRs.\n", file=stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watchlist", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--previous-release", help="full commit SHA of the pinned comparison release")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        if args.previous_release and (args.previous is None or not re.fullmatch(r"[0-9a-f]{40}", args.previous_release)):
            raise ValueError("previous release identity requires a full SHA and retained inputs")
        watch = read_watchlist(args.watchlist)
        candidate = verified_snapshot(args.candidate, watch)
        previous = verified_snapshot(args.previous, watch) if args.previous is not None else None
        rows = compare(watch, previous, candidate)
        report = {
            "schema": 1, "mode": "REPORT_ONLY", "watchlist_sha256": describe(args.watchlist)["sha256"],
            "previous_release": args.previous_release,
            "previous_sha256": previous["hashes"] if previous else None, "candidate_sha256": candidate["hashes"],
            "scope": "ipverse observation window, not real-time BGP, geography, reachability or service ownership",
            "direct_impact_summary": summarize_impact(rows),
            "observed_snapshot_identity": summarize_observed_changes(watch, previous, candidate),
            "rows": rows,
        }
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, sort_keys=True, ensure_ascii=False, indent=2)
            stream.write("\n")
        if args.summary:
            with args.summary.open("a", encoding="utf-8") as stream:
                write_summary(report, stream)
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, EOFError) as exc:
        parser.exit(1, f"priority ASN audit unavailable: {exc}\n")


if __name__ == "__main__":
    main()
