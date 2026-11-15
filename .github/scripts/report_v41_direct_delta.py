#!/usr/bin/env python3
"""Report exact RU/DIRECT changes against a pinned v41 release without gating it."""
import argparse
import json
from pathlib import Path
import re

from build_v41_overlay import intersect, intervals, networks_from_intervals, subtract
from v41_reviewed_ipv6_admission import RECORD_KEY, verify_reviewed_ipv6_admission_manifest
from validate_v41_publication_bounds import read, total


def scope(ranges, family):
    return {
        "addresses": str(total(ranges)),
        "cidrs": [str(net) for net in sorted(networks_from_intervals(ranges, family))],
    }


def make_report(reference, checksum, revision, candidate, manifest, table):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("expected a full baseline release commit SHA")
    old, old_sha = read(reference)
    if checksum.read_bytes() != f"{old_sha}  geoip_RU.dat\n".encode("ascii"):
        raise ValueError("baseline release DAT does not match its checksum")
    new, new_sha = read(candidate)
    policy = json.loads(manifest.read_text(encoding="utf-8"))
    if policy.get("output_sha256") != new_sha:
        raise ValueError("candidate policy manifest does not bind the DAT")
    reviewed = verify_reviewed_ipv6_admission_manifest(table, policy)
    reviewed_space = intervals(reviewed, 6)
    if intersect(new["RU"][6], reviewed_space):
        raise ValueError("candidate DIRECT intersects reviewed IPv6 exclusions")

    direct = {}
    for family in (4, 6):
        before, after = old["RU"][family], new["RU"][family]
        direct[f"ipv{family}"] = {
            "added": scope(subtract(after, before), family),
            "removed": scope(subtract(before, after), family),
        }
    removed6 = subtract(old["RU"][6], new["RU"][6])
    reviewed_rows = []
    for net, record in sorted(reviewed.items()):
        removed_here = intersect(removed6, intervals([net], 6))
        if removed_here:
            reviewed_rows.append({
                "policy_prefix": str(net),
                "origin_asn": record["origin_asn"],
                "removed": scope(removed_here, 6),
            })

    unmatched = scope(subtract(removed6, reviewed_space), 6)
    return {
        "schema": 1,
        "mode": "ADVISORY",
        "baseline": {"release_commit": revision, "dat_sha256": old_sha},
        "candidate_dat_sha256": new_sha,
        "reviewed_ipv6_policy_sha256": policy["input_sha256"][RECORD_KEY],
        "direct": direct,
        "private_changed": {
            f"ipv{family}": old["PRIVATE"][family] != new["PRIVATE"][family]
            for family in (4, 6)
        },
        "ipv6_removals": {
            "covered_by_reviewed_policy": scope(intersect(removed6, reviewed_space), 6),
            "reviewed_policy_rows": reviewed_rows,
            "outside_reviewed_policy": unmatched,
        },
    }


def write_summary(report, stream):
    print("### v41 DIRECT delta against the published release", file=stream)
    print(f"Baseline release commit: `{report['baseline']['release_commit']}`\n", file=stream)
    for family, changes in report["direct"].items():
        print(f"- IPv{family[-1]} addresses: +{changes['added']['addresses']} / "
              f"−{changes['removed']['addresses']}", file=stream)
    if any(report["private_changed"].values()):
        print("- PRIVATE changed in at least one family (review separately)", file=stream)
    ipv6 = report["ipv6_removals"]
    for name, label in (
        ("covered_by_reviewed_policy", "IPv6 removals covered by the reviewed table"),
        ("outside_reviewed_policy", "IPv6 removals outside the reviewed table (investigate)"),
    ):
        data = ipv6[name]
        print(f"- {label}: {data['addresses']} addresses across {len(data['cidrs'])} CIDRs", file=stream)
        if data["cidrs"]:
            print("  - " + ", ".join(f"`{cidr}`" for cidr in data["cidrs"][:20]), file=stream)
    print("\nAdvisory only. The Actions artifact contains all CIDRs. "
          "A removal outside the table is not proof of an outage.", file=stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "reference-checksum", "candidate", "manifest", "table", "output", "summary"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--reference-commit", required=True)
    args = parser.parse_args()
    try:
        report = make_report(args.reference, args.reference_checksum, args.reference_commit,
                             args.candidate, args.manifest, args.table)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with args.summary.open("a", encoding="utf-8") as stream:
            write_summary(report, stream)
        if report["ipv6_removals"]["outside_reviewed_policy"]["cidrs"]:
            print("::warning::IPv6 removals outside the reviewed table. See the DIRECT delta report.")
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        parser.exit(1, f"Could not complete DIRECT delta report: {exc}\n")


if __name__ == "__main__":
    main()
