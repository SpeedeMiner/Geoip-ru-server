from datetime import date
import ipaddress
from pathlib import Path
import json
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

import audit_v41_prefix_candidates as audit
from build_v41_overlay import encode_geoip
from validate_v41_publication_bounds import read


class PrefixCandidateTests(unittest.TestCase):
    def test_command_writes_report_and_summary_for_a_synthetic_dat(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            dat = root / "candidate.dat"
            dat.write_bytes(encode_geoip({
                "RU": {ipaddress.ip_network("198.51.100.0/25"), ipaddress.ip_network("2001:db8::/48")},
                "PRIVATE": {ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("fc00::/7")},
            }))
            candidates = root / "candidates.tsv"
            candidates.write_text("\t".join(audit.HEADER) + "\n" +
                "198.51.100.0/24\tAS123\texample\t2020-01-01\t2099-01-01\t"
                "https://example.test/bgp\thttps://example.test/rdap\n", encoding="utf-8")
            output, summary = root / "report.json", root / "summary.md"
            subprocess.run([sys.executable, audit.__file__, "--dat", str(dat), "--candidates", str(candidates),
                            "--output", str(output), "--summary", str(summary)], check=True, capture_output=True)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["role"], "advisory-no-routing-change")
            self.assertEqual(report["candidates"][0]["direct_addresses"], "128")
            self.assertIn(report["candidate_sha256"], summary.read_text(encoding="utf-8"))

    def test_real_candidate_is_explicitly_advisory(self):
        path = Path(__file__).resolve().parent.parent / "data/v41-coverage-candidates.tsv"
        rows = audit.read_candidates(path, as_of=date(2026, 11, 16))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["origin_asn"], "AS35673")
        self.assertFalse(rows[0]["review_due"])

    def test_partial_coverage_is_measured_by_addresses_not_prefix_count(self):
        with TemporaryDirectory() as folder:
            dat = Path(folder) / "test.dat"
            data = {"RU": {ipaddress.ip_network("198.51.100.0/25"), ipaddress.ip_network("2001:db8::/48")},
                    "PRIVATE": {ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("fc00::/7")}}
            dat.write_bytes(encode_geoip(data))
            categories, _ = read(dat)
            row = {"prefix": "198.51.100.0/24", "origin_asn": "AS123", "service": "example",
                   "observed_on": "2026-11-16", "review_after": "2027-01-01", "review_due": False}
            result = audit.coverage(categories, [row])[0]
            self.assertEqual(result["coverage"], "PARTIAL")
            self.assertEqual(result["direct_addresses"], "128")
            self.assertEqual(result["non_direct_addresses"], "128")
            self.assertIn("not reachability", audit.format_report([result], "a" * 64))

    def test_rejects_duplicate_and_future_evidence(self):
        row = ("198.51.100.0/24\tAS123\texample\t2026-11-16\t2027-01-01\t"
               "https://example.test/bgp\thttps://example.test/rdap\n")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "candidate.tsv"
            for body in (row + row, row.replace("2026-11-16", "2026-11-17"), row.replace("AS123", "AS0")):
                path.write_text("\t".join(audit.HEADER) + "\n" + body, encoding="utf-8")
                with self.assertRaises(ValueError):
                    audit.read_candidates(path, as_of=date(2026, 11, 16))
