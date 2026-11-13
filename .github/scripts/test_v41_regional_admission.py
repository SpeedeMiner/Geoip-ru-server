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
            "145.249.0.0/18", "145.249.64.0/19", "145.249.96.0/21",
            "185.17.120.0/22", "185.49.68.0/22", "195.54.32.0/23",
        })
        self.assertEqual({row["origin_asn"] for row in rows.values()}, {"AS28753", "AS29256", "AS211095"})

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
