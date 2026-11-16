import csv
import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import build_v41_overlay as builder
import report_v41_pr_delta as report


class PullRequestReportTests(unittest.TestCase):
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
