import ipaddress
import tempfile
import unittest
from pathlib import Path

from audit_v41_legacy_hard_evidence import audit, tagged_networks


def nets(*values):
    return {ipaddress.ip_network(value) for value in values}


class LegacyHardEvidenceTests(unittest.TestCase):
    def test_current_resolver_separated_from_historical_resolver(self):
        hard = [
            (ipaddress.ip_network("198.51.100.1/32"), {"v38-baseline-hard-or-unclassified"}),
            (ipaddress.ip_network("198.51.100.2/32"), {"v38-baseline-hard-or-unclassified"}),
            (ipaddress.ip_network("198.51.100.3/32"), {"v38-baseline-hard-or-unclassified", "antifilter-ip.lst"}),
            (ipaddress.ip_network("198.51.100.4/32"), {"v38-baseline-hard-or-unclassified"}),
        ]
        resolver = [
            (ipaddress.ip_network("198.51.100.1/32"), {"v38-historical-ipresolve-only"}),
            (ipaddress.ip_network("198.51.100.2/32"), {"antifilter-ipresolve.lst"}),
        ]
        rows, s = audit(hard, resolver, nets("198.51.100.1/32", "198.51.100.2/32"),
                        nets("198.51.100.0/24"), nets("198.51.100.3/32"))
        self.assertEqual(s["legacy_only_hard_rows"], 3)
        self.assertEqual(s["legacy_only_v34_lost"], 3)
        self.assertEqual(s["legacy_only_v34_lost_absent_current_resolver"], 2)
        self.assertEqual(s["legacy_only_absent_current_resolver"], 2)
        self.assertEqual(s["legacy_only_not_effective"], 1)
        self.assertEqual({r["prefix"] for r in rows}, {
            "198.51.100.1/32", "198.51.100.2/32", "198.51.100.4/32"})
        self.assertEqual(rows[0]["historical_resolver"], "YES")
        self.assertEqual(rows[0]["current_resolver"], "NO")
        self.assertEqual(rows[1]["review_priority"], "MEDIUM")

    def test_unrecognized_provenance_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hard.txt"
            path.write_text("192.0.2.1/32\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing provenance"):
                tagged_networks(path)

    def test_legacy_wide_mask_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "not IPv4 /32"):
            audit([(ipaddress.ip_network("198.51.100.0/24"), {"v38-baseline-hard-or-unclassified"})],
                  [], set(), set(), set())


if __name__ == "__main__":
    unittest.main()
