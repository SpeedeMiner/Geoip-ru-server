#!/usr/bin/env python3
"""Compare eligible live block-feed counts against the pinned previous release."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

REQUIRED = ("antifilter-ip.lst", "antifilter-ipresolve.lst", "antifilter-subnet.lst")
FALLBACK = "EMPTY_FALLBACK_V38_PINNED_BASELINE"
HEADER = ["SOURCE", "STATUS", "DATA_LINES", "VALID_UNIQUE_PREFIXES",
          "APPROVED_PREFIXES", "REVIEW_PREFIXES", "INVALID_LINES"]


def read_stats(path):
    counts = {}
    with path.open(encoding="utf-8", newline="") as stream:
        rows = csv.DictReader(stream, delimiter="\t")
        if rows.fieldnames != HEADER:
            raise ValueError(f"{path}: unexpected blocked-feed stats header")
        for row in rows:
            name = row["SOURCE"]
            if name not in REQUIRED:
                continue
            if name in counts or None in row:
                raise ValueError(f"{path}: duplicate or malformed stats row for {name}")
            status = row["STATUS"]
            try:
                approved = int(row["APPROVED_PREFIXES"])
                unique = int(row["VALID_UNIQUE_PREFIXES"])
                lines = int(row["DATA_LINES"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}: invalid counts for {name}") from exc
            if not 0 <= approved <= unique <= lines:
                raise ValueError(f"{path}: inconsistent counts for {name}")
            if status == FALLBACK:
                if name != "antifilter-ipresolve.lst" or (approved, unique, lines) != (0, 0, 0):
                    raise ValueError(f"{path}: invalid fallback for {name}")
            elif status != "AVAILABLE":
                raise ValueError(f"{path}: unknown status for {name}: {status}")
            counts[name] = (status, approved)
    if counts.keys() != set(REQUIRED):
        raise ValueError(f"{path}: missing blocked-feed stats rows: {sorted(set(REQUIRED) - counts.keys())}")
    return counts


def compare_counts(previous, candidate):
    results = []
    for name in REQUIRED:
        old_status, old = previous[name]
        new_status, new = candidate[name]
        row = {"source": name, "previous": old, "candidate": new, "delta": new - old}
        if new_status == FALLBACK:
            row["verdict"] = "resolver-fallback-v38"
        elif old_status == FALLBACK or old == 0:
            row["verdict"] = "no-usable-prior-count"
        elif 2 * abs(new - old) > old:
            row["verdict"] = "abrupt-count-change"
        else:
            row["verdict"] = "ok"
        results.append(row)
    return results


def review_digest(stats, feeds):
    # Bind the review to the statistics and to the source bytes, not just counts.
    digest = hashlib.sha256(b"geoip-v41-block-feed-review-v1\n")
    for label, path in zip(("stats", *REQUIRED), (stats, *feeds), strict=True):
        with path.open("rb") as stream:
            digest.update(f"{label} {hashlib.file_digest(stream, 'sha256').hexdigest()}\n".encode("ascii"))
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--feeds", type=Path, nargs=3, required=True, metavar=("IP", "IPRESOLVE", "SUBNET"))
    parser.add_argument("--reviewed-sha256", default="")
    args = parser.parse_args()
    try:
        results = compare_counts(read_stats(args.previous), read_stats(args.candidate))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"ERROR: blocked-feed comparison: {exc}\n")
    for row in results:
        print(json.dumps(row, sort_keys=True))
    unusual = [row["source"] for row in results if row["verdict"] == "abrupt-count-change"]
    if unusual:
        try:
            sha = review_digest(args.candidate, args.feeds)
        except OSError as exc:
            parser.exit(1, f"ERROR: unable to digest review inputs: {exc}\n")
        if args.reviewed_sha256 != sha:
            parser.exit(1, "ERROR: approved prefix count changed by more than 50% since the previous "
                        "release: " + ", ".join(unusual) + f". Review candidate input SHA-256 {sha}\n")
        print(f"Reviewed block-feed input SHA-256 accepted: {sha}")


if __name__ == "__main__":
    main()
