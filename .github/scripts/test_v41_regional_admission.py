import ipaddress
import tempfile
import unittest
from pathlib import Path

from build_v41_overlay import (
    assert_regional_admission_disjoint,
    parse_regional_admission_exclusions,
    subtract_networks,
)


class RegionalAdmissionTests(unittest.TestCase):
    header = "prefix\tdelegated_country\tassignment_country\torigin_asn\tchecked_on\n"

    def test_prefix_exclusion_preserves_neighbors_and_ipv6(self):
        covering = ipaddress.ip_network("185.49.64.0/20")
        foreign = ipaddress.ip_network("185.49.68.0/22")
        ipv6 = ipaddress.ip_network("2a00:abcd::/32")
        before = {covering, ipv6}
        after = subtract_networks(before, {foreign})
        self.assertEqual(after, {ipaddress.ip_network("185.49.64.0/22"),
                                 ipaddress.ip_network("185.49.72.0/21"), ipv6})
        assert_regional_admission_disjoint(after, {foreign})
        with self.assertRaisesRegex(ValueError, "DIRECT intersects reviewed regional admission"):
            assert_regional_admission_disjoint(before, {foreign})

    def test_real_input_contains_only_exact_reviewed_prefixes(self):
        path = Path(__file__).resolve().parent.parent / "data/v41-regional-admission-exclusions.tsv"
        rows = parse_regional_admission_exclusions(path)
        self.assertEqual({str(n) for n in rows}, {
            "31.204.8.0/21", "31.204.16.0/21", "31.204.32.0/20", "31.204.56.0/21",
            "109.238.168.0/21", "212.124.106.0/24",
            "145.249.0.0/18", "145.249.64.0/19", "145.249.96.0/21",
            "185.17.120.0/22", "185.49.68.0/22", "195.54.32.0/23",
        })
        for prefix, delegated, assignment, origin in (
            ("31.204.8.0/21", "RU", "US", "AS209372"),
            ("31.204.16.0/21", "RU", "US", "AS213541"),
            ("31.204.32.0/20", "RU", "AU", "AS213541"),
            ("31.204.56.0/21", "RU", "AU", "AS213541"),
            ("109.238.168.0/21", "KZ", "US", "AS26548"),
            ("212.124.106.0/24", "RU", "US", "AS47328"),
        ):
            self.assertEqual(rows[ipaddress.ip_network(prefix)], {
                "prefix": prefix, "delegated_country": delegated, "assignment_country": assignment,
                "origin_asn": origin, "checked_on": "2026-11-13",
            })

    def test_us_assignments_do_not_remove_other_routes_from_same_parent(self):
        before = {ipaddress.ip_network(p) for p in ("31.204.0.0/18", "109.238.160.0/20")}
        excluded = {ipaddress.ip_network(p) for p in ("31.204.8.0/21", "109.238.168.0/21")}
        after = subtract_networks(before, excluded)
        self.assertEqual(after, {ipaddress.ip_network(p) for p in (
            "31.204.0.0/21", "31.204.16.0/20", "31.204.32.0/19", "109.238.160.0/21",
        )})
        assert_regional_admission_disjoint(after, excluded)

    def test_digitalone_exclusion_does_not_widen_to_mnogobyte_parent(self):
        parent = ipaddress.ip_network("212.124.96.0/19")
        exact = ipaddress.ip_network("212.124.106.0/24")
        after = subtract_networks({parent}, {exact})
        self.assertEqual(after, set(parent.address_exclude(exact)))
        assert_regional_admission_disjoint(after, {exact})

    def test_invalid_row_cannot_widen_mask(self):
        row = "185.49.68.0/22\tBY\tDE\tAS28753\t2026-11-13\n"
        for payload in (
            row + row,
            row + row.replace("68.0/22", "68.0/24"),
            row.replace("185.49.68.0/22", "185.0.0.0/8"),
            row.replace("185.49.68.0/22", "185.49.68.1/22"),
            row.replace("185.49.68.0/22", "2a00:abcd::/32"),
            row.replace("DE", "RU"),
            row.replace("AS28753", "AS028753"),
            row.replace("2026-11-13", "2026-02-31"),
            row.rstrip() + "\textra\n",
        ):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "regional.tsv"
                p.write_text(self.header + payload)
                with self.assertRaisesRegex(ValueError, "invalid regional admission exclusion"):
                    parse_regional_admission_exclusions(p)
