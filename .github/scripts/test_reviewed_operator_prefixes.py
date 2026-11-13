import ipaddress
from pathlib import Path
import tempfile
import unittest

from build_v41_overlay import (
    assert_reviewed_operator_coverage, class_aware_effective_block_set,
    parse_reviewed_operator_prefixes, reviewed_operator_provenance, subtract_networks,
)


class ReviewedOperatorPrefixesTests(unittest.TestCase):
    def parse(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.tsv"
            path.write_text("country\tprefix\torigin_asn\n" + rows, encoding="utf-8")
            return parse_reviewed_operator_prefixes(path)

    def test_exact_network_and_asn_are_preserved(self):
        self.assertEqual(self.parse("RU\t153.52.151.0/24\tAS402931\n"),
                         {ipaddress.ip_network("153.52.151.0/24"): ("RU", "AS402931")})

    def test_exact_ipv6_pop_and_existing_ipv4_can_coexist(self):
        rows = self.parse("RU\t153.52.151.0/24\tAS402931\nRU\t2001:ad0:2000:1::/64\tAS3327\n")
        self.assertEqual(rows, {ipaddress.ip_network("153.52.151.0/24"): ("RU", "AS402931"),
                                ipaddress.ip_network("2001:ad0:2000:1::/64"): ("RU", "AS3327")})
        provenance = reviewed_operator_provenance(rows, "reviewed")
        self.assertEqual([(row["prefix"], row["asn_list"]) for row in provenance],
                         [("153.52.151.0/24", "AS402931"), ("2001:ad0:2000:1::/64", "AS3327")])

    def test_rejects_malformed_or_excessive_routes(self):
        for row in ("RU\t153.52.151.1/24\tAS402931", "RU\t153.52.151.0\tAS402931",
                    "RU\t153.52.0.0/16\tAS402931", "RU\t2a13::/48\tAS402931",
                    "US\t153.52.151.0/24\tAS402931", "RU\t10.0.0.0/24\tAS402931",
                    "RU\t224.0.0.0/24\tAS402931",
                    "RU\t2001:ad0::/32\tAS3327", "RU\t2001:ad0:2000:1::1/64\tAS3327",
                    "RU\tff02::/64\tAS3327", "RU\t::ffff:808:808/128\tAS3327",
                    "RU\t153.52.151.0/24\tAS0", "RU\t153.52.151.0/24\tAS0402931",
                    "RU\t153.52.151.0/24\tAS402931\textra", ""):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.parse(row + "\n")

    def test_rejects_overlap_and_duplicate(self):
        row = "RU\t153.52.150.0/23\tAS402931\n"
        for extra in (row, "BY\t153.52.151.0/24\tAS207957\n"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.parse(row + extra)


    def test_resolver_only_protection_does_not_extend_to_neighbors_or_hard(self):
        def nets(*rows):
            return {ipaddress.ip_network(row) for row in rows}

        reviewed = set(self.parse(
            "RU\t153.52.151.0/24\tAS402931\nRU\t2001:ad0:2000:1::/64\tAS3327\n"
        ))
        inside = nets("153.52.151.3/32", "2001:ad0:2000:1::3/128")
        outside = nets("153.52.152.3/32", "2001:ad0:2000:2::3/128")
        hard = nets("153.52.151.5/32", "2001:ad0:2000:1::5/128")
        unconditional = nets("153.52.151.6/32")
        effective, _ = class_aware_effective_block_set(
            hard, inside | outside | hard, set(), set(), non_exempt=unconditional,
            reviewed_operator_prefixes=reviewed,
        )
        self.assertEqual(effective, outside | hard | unconditional)
        private = nets("153.52.151.7/32")
        admission = nets("153.52.151.128/25")
        hard |= unconditional
        direct = subtract_networks(reviewed, private, hard | admission)
        assert_reviewed_operator_coverage(direct, private, hard, admission, reviewed)
        for host in inside:
            with self.subTest(host=host), self.assertRaisesRegex(ValueError, "Reviewed operator"):
                assert_reviewed_operator_coverage(
                    subtract_networks(direct, {host}), private, hard, admission, reviewed,
                )
