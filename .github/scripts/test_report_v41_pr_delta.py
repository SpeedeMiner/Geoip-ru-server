import csv
import hashlib
import ipaddress
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import build_v41_overlay as builder
import report_v41_pr_delta as report
from v41_reviewed_ipv6_admission import RECORD_KEY, read_reviewed_ipv6_admission


class PullRequestReportTests(unittest.TestCase):
    def exact_inputs(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        table = Path(__file__).resolve().parents[1] / "data/v41-reviewed-ipv6-admission-exclusions.tsv"
        old, new, sidecar, manifest = (root / name for name in ("old", "new", "sha", "manifest"))
        for path, cidrs, private4 in (
            (old, ("192.0.2.0/25", "2001:db8::/48", "2a0b:4e07:6310::/48"), "10.0.0.0/8"),
            (new, ("192.0.2.64/26", "192.0.2.128/25", "2001:db8::/48", "2a0b:4e07:63f0::/47"), "10.0.0.0/9"),
        ):
            path.write_bytes(builder.encode_geoip({
                "RU": set(map(ipaddress.ip_network, cidrs)),
                "PRIVATE": {ipaddress.ip_network(private4), ipaddress.ip_network("fc00::/7")},
            }))
        sidecar.write_text(f"{hashlib.sha256(old.read_bytes()).hexdigest()}  geoip_RU.dat\n", encoding="ascii")
        manifest.write_text(json.dumps({
            "output_sha256": hashlib.sha256(new.read_bytes()).hexdigest(),
            "input_sha256": {RECORD_KEY: hashlib.sha256(table.read_bytes()).hexdigest()},
            RECORD_KEY: {"role": "geography-review-only",
                         "records": list(read_reviewed_ipv6_admission(table).values())},
        }), encoding="utf-8")
        return new, old, sidecar, manifest, table, "a" * 40

    def test_exact_delta_keeps_geography_review_only_and_splits_reporting(self):
        delta = report.exact_delta(*self.exact_inputs())
        self.assertEqual(delta["mode"], "ADVISORY")
        self.assertEqual(delta["private_changed"], {"ipv4": True, "ipv6": False})
        self.assertEqual(delta["direct"]["ipv4"], {
            "added": {"addresses": "128", "cidrs": ["192.0.2.128/25"]},
            "removed": {"addresses": "64", "cidrs": ["192.0.2.0/26"]},
        })
        self.assertEqual(delta["direct"]["ipv6"]["added"], {
            "addresses": str(2**81), "cidrs": ["2a0b:4e07:63f0::/47"],
        })
        self.assertEqual(
            [(row["assignment_country"], row["added"]["addresses"], row["removed"]["addresses"])
             for row in delta["ipv6_geography"]["changed_overlaps"]],
            [("DE", "0", str(2**80)), ("KP", str(2**80), "0"), ("IN", str(2**80), "0")],
        )

    def test_exact_delta_requires_pinned_release_and_exact_sidecar(self):
        args = self.exact_inputs()
        with self.assertRaisesRegex(ValueError, "full release commit"):
            report.exact_delta(*args[:-1], "release")
        args[2].write_bytes(args[2].read_bytes() + b"extra\n")
        with self.assertRaisesRegex(ValueError, "checksum sidecar"):
            report.exact_delta(*args)

    def test_exact_delta_rejects_unbound_candidate_or_evidence(self):
        args = self.exact_inputs()
        p = args[3]
        valid = json.loads(p.read_bytes())
        for malformed, error in (
            ({**valid, "output_sha256": "0" * 64}, "manifest does not bind"),
            ({**valid, "input_sha256": {}}, "provenance mismatch"),
            ({**valid, RECORD_KEY: {**valid[RECORD_KEY], "role": "active-mask"}}, "unrecognized"),
        ):
            with self.subTest(error=error):
                p.write_text(json.dumps(malformed), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, error):
                    report.exact_delta(*args)

    def test_reports_real_changes_and_source_metrics(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            def dat(name, ipv4):
                path = root / name
                path.write_bytes(builder.encode_geoip({
                    "RU": {ipaddress.ip_network(ipv4), ipaddress.ip_network("2001:db8::/48")},
                    "PRIVATE": {ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("fc00::/7")},
                }))
                return path
            def source(name, size):
                path = root / name
                with path.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.writer(stream, delimiter="\t")
                    writer.writerow(("source_id", "unique_cidrs", "ipv4_addresses", "ipv6_addresses"))
                    for key in report.SOURCES:
                        writer.writerow((key, size, size * 256, size * 65536))
                return path
            result = report.report(dat("new.dat", "198.18.0.0/24"), dat("old.dat", "198.18.0.0/25"),
                                   source("new.tsv", 2), source("old.tsv", 1), "a" * 40)
            self.assertIn("| IPv4 | 128 | 256 | 128 | 0 | 1 | 1 |", result)
            self.assertIn("| hydra-direct | 1 → 2 | 256 → 512 |", result)
            self.assertIn("не суммируются", result)

    def test_rejects_missing_source_metrics(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing.tsv"
            path.write_text("source_id\tunique_cidrs\tipv4_addresses\tipv6_addresses\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing source"):
                report.metrics(path)
