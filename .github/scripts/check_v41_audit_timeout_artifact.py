#!/usr/bin/env python3
"""Exercise actual audit timeouts on local synthetic inputs and verify the CI artifact."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

import build_priority_prefix_evidence as audit
from test_build_priority_prefix_evidence import make_row

PREFIX = "192.0.2.0/24"
ORIGINS = {"AS64500", "AS64501"}
FILES = {
    "RDAP": ("rdap_samples_partial.tsv",),
    "RPKI": ("rpki_by_origin_partial.tsv",),
    "IRR": ("irr_prefix_summary_partial.tsv", "irr_route_objects_partial.tsv"),
}
MANIFEST = "timeout_fixture_manifest.json"


def simulate(phase, path):
    row = make_row(PREFIX, "AS64500", "AS64500,AS64501", "yes", "COMPANY_ASN_ONLY")
    queue = path / "company.tsv"
    with queue.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows([row, {**row, "PREFIX": "198.51.100.0/24"}])

    original = audit.completed_queries

    def stop_after_first(marker, futures):
        if marker != phase:
            yield from original(marker, futures)
            return
        yield next(iter(futures))
        # An actual external deadline stops the collector only after its first flush.
        time.sleep(30)
        raise AssertionError("fixture was not stopped by timeout")

    def rdap(prefix, address, _entries):
        return {"PREFIX": prefix, "SAMPLE_ADDRESS": address, "QUERY_STATUS": "OK"}

    def irr(prefix, _sources, _origins):
        return "OK", "https://example.invalid/irr", [{
            "QUERY_PREFIX": prefix, "OBJECT_TYPE": "route", "ROUTE_PREFIX": prefix,
            "ORIGIN_ASN": "AS64500", "REGISTRY_SOURCE": "RIPE", "EXACT_PREFIX_MATCH": "yes",
            "GLOBAL_BGP_ORIGIN_MATCH": "yes", "MNT_BY": "", "ORG": "", "DESCR": "",
        }]

    with (
        patch.object(audit, "request_json_with_bytes", return_value=(503, None, "fixture", None)),
        patch.object(audit, "request_json", return_value=(503, None, "fixture")),
        patch.object(audit, "fetch_rdap_sample", side_effect=rdap),
        patch.object(audit, "fetch_rpki_origin", side_effect=TimeoutError("fixture")),
        patch.object(audit, "fetch_irr_prefix", side_effect=irr),
        patch.object(audit, "completed_queries", side_effect=stop_after_first),
    ):
        audit.build_evidence(queue, path / "evidence", max_workers=2)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path):
    expected = {f for files in FILES.values() for f in files}
    if {item.name for item in path.iterdir()} != expected | {MANIFEST}:
        raise ValueError("unexpected timeout artifact file inventory")
    manifest = json.loads((path / MANIFEST).read_text(encoding="utf-8"))
    if manifest != {
        "kind": "synthetic-timeout-fixture",
        "exit_status": dict.fromkeys(FILES, 124),
        "sha256": {name: digest(path / name) for name in sorted(expected)},
    }:
        raise ValueError("timeout status or artifact digest mismatch")

    def only_row(name):
        with (path / name).open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t", strict=True))
        if len(rows) != 1 or None in rows[0] or None in rows[0].values():
            raise ValueError(f"{name}: expected one complete diagnostic record")
        return rows[0]

    r = only_row(FILES["RDAP"][0])
    if (r["PREFIX"], r["SAMPLE_ADDRESS"], r["QUERY_STATUS"]) != (PREFIX, "192.0.2.0", "OK"):
        raise ValueError("RDAP diagnostic row mismatch")
    r = only_row(FILES["RPKI"][0])
    if r["PREFIX"] != PREFIX or r["ORIGIN_ASN"] not in ORIGINS or r["RPKI_STATUS"] or r["QUERY_STATUS"] != "CLIENT_ERROR:TimeoutError:fixture":
        raise ValueError("RPKI timeout must not masquerade as a RPKI status")
    r = only_row(FILES["IRR"][0])
    if (r["PREFIX"], r["QUERY_STATUS"], r["IRR_SOURCE_OBJECT_RECORDS"]) != (PREFIX, "OK", "1"):
        raise ValueError("IRR summary mismatch")
    r = only_row(FILES["IRR"][1])
    if (r["QUERY_PREFIX"], r["ROUTE_PREFIX"], r["ORIGIN_ASN"]) != (PREFIX, PREFIX, "AS64500"):
        raise ValueError("IRR route object mismatch")
    print("Verified four partial TSVs and all three forced timeout statuses.", flush=True)


def produce(path):
    path.mkdir()
    with TemporaryDirectory() as directory:
        def run(phase):
            root = Path(directory) / phase
            root.mkdir()
            code = subprocess.run(
                ["timeout", "--kill-after=1s", "3s", sys.executable, "-u", __file__,
                 "simulate", str(root), "--phase", phase],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=6,
            )
            if code.returncode != 124:
                raise ValueError(f"{phase}: expected timeout status 124, got {code.returncode}\n{code.stdout}")
            for name in FILES[phase]:
                evidence = root / "evidence"
                if (evidence / name.replace("_partial", "")).exists():
                    raise ValueError(f"{phase}: partial fixture emitted a canonical TSV")
                shutil.copyfile(evidence / name, path / name)
            return (phase, code.returncode)

        with ThreadPoolExecutor(max_workers=3) as pool:
            status = dict(pool.map(run, FILES))
    manifest = {
        "kind": "synthetic-timeout-fixture",
        "exit_status": status,
        "sha256": {p.name: digest(p) for p in sorted(path.iterdir())},
    }
    (path / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("produce", "verify", "simulate"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--phase", choices=FILES)
    args = parser.parse_args()
    if (args.mode == "simulate") != (args.phase is not None):
        parser.error("--phase is required for simulate only")
    if args.mode == "simulate":
        simulate(args.phase, args.directory)
    else:
        {"produce": produce, "verify": verify}[args.mode](args.directory)


if __name__ == "__main__":
    main()
