import ipaddress
import tempfile
import unittest
from pathlib import Path

from audit_v41_other_current_hard_ris import expand_selected, build_rows
from audit_v41_current_hard_ris import annotate


class OtherHardOriginSelectionTests(unittest.TestCase):
    def test_expand_exact_cidrs_and_select_current_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "other.txt"
            p.write_text("192.0.2.4/31\n198.51.100.1/32\n")
            selected = expand_selected(p)
            self.assertEqual(selected, ["192.0.2.4", "192.0.2.5", "198.51.100.1"])
            hard = [(ipaddress.ip_network("192.0.2.4/31"), {"antifilter-ip.lst"}),
                    (ipaddress.ip_network("198.51.100.1/32"), {"v38-baseline-hard-or-unclassified"})]
            records = build_rows(selected, hard)
            observed, s = annotate(records, lambda _: {"status": "ok", "data":
                                   {"prefix": "192.0.2.0/24", "asns": [64501]}},
                                   sleep_seconds=0)
            self.assertEqual(len(observed), 2)
            self.assertEqual(s["ris_observed"], 2)

    def test_reject_host_without_hard_evidence(self):
        with self.assertRaisesRegex(ValueError, "not in the original hard mask"):
            build_rows(["192.0.2.8"], [])

    def test_reject_overbroad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "other.txt"
            p.write_text("192.0.2.0/24\n")
            with self.assertRaisesRegex(ValueError, "Too many"):
                expand_selected(p, max_addresses=50)


if __name__ == "__main__":
    unittest.main()
