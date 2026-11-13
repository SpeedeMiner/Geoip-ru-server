import ipaddress
from pathlib import Path
import tempfile
import unittest

from build_v41_overlay import parse_reviewed_operator_prefixes


class ReviewedOperatorPrefixesTests(unittest.TestCase):
    def parse(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.tsv"
            path.write_text("country\tprefix\torigin_asn\n" + rows, encoding="utf-8")
            return parse_reviewed_operator_prefixes(path)

    def test_exact_network_and_asn_are_preserved(self):
        self.assertEqual(self.parse("RU\t153.52.151.0/24\tAS402931\n"),
                         {ipaddress.ip_network("153.52.151.0/24"): ("RU", "AS402931")})

    def test_rejects_malformed_or_excessive_routes(self):
        for row in ("RU\t153.52.151.1/24\tAS402931", "RU\t153.52.151.0\tAS402931",
                    "RU\t153.52.0.0/16\tAS402931", "RU\t2a13::/48\tAS402931",
                    "US\t153.52.151.0/24\tAS402931", "RU\t10.0.0.0/24\tAS402931",
                    "RU\t224.0.0.0/24\tAS402931",
                    "RU\t153.52.151.0/24\tAS0", "RU\t153.52.151.0/24\tAS0402931",
                    "RU\t153.52.151.0/24\tAS402931\textra", ""):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.parse(row + "\n")

    def test_rejects_overlap_and_duplicate(self):
        row = "RU\t153.52.150.0/23\tAS402931\n"
        for extra in (row, "BY\t153.52.151.0/24\tAS207957\n"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.parse(row + extra)
