import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from v41_static_overrides import expected_quality_markers, read_overrides, unobserved


class StaticOverrideTests(unittest.TestCase):
    def test_quality_markers_are_generated_for_all_configured_prefixes(self):
        markers = expected_quality_markers({"2001:db8::/48": {}, "192.0.2.0/24": {}, "198.51.100.0/24": {}})
        self.assertEqual(markers[0], "Static DIRECT override list: 192.0.2.0/24, 198.51.100.0/24, 2001:db8::/48")
        self.assertIn("3 of 3", markers[2])
        self.assertTrue(markers[3].endswith("192.0.2.0/24, 198.51.100.0/24, 2001:db8::/48"))

    def test_observation_requires_same_origin_and_may_be_aggregate(self):
        rows = {"192.0.2.0/24": {"asn_number": 123}, "2001:db8::/48": {"asn_number": 123}}
        observed = {"192.0.2.0/23": {123}, "2001:db8::/32": {124}}
        self.assertEqual([prefix for prefix, _ in unobserved(rows, observed)], ["2001:db8::/48"])
        observed = {"192.0.2.0/25": {123}, "192.0.2.128/25": {123}, "2001:db8::/48": {123}}
        self.assertEqual(list(unobserved(rows, observed)), [])

    def test_registry_rejects_default_duplicate_and_bad_metadata(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "overrides.tsv"
            header = "cidr\tasn\treason\tadded_date\treview_after\n"
            valid = "192.0.2.0/24\tAS123\texample\t2026-11-16\t2027-01-01\n"
            path.write_text(header + valid, encoding="utf-8")
            self.assertEqual(read_overrides(path)["192.0.2.0/24"]["asn_number"], 123)
            for text in (header + valid + valid,
                         header + "0.0.0.0/0\tAS123\texample\t2026-11-16\t2027-01-01\n",
                         header + "192.0.2.0/24\tAS123\texample\t2026-11-16\t2020-01-01\n"):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_overrides(path)
