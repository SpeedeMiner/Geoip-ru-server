import ipaddress
import tempfile
import unittest
from pathlib import Path

from audit_v41_shared_hard_guard import load_observed_baseline, scan


def nets(*values):
    return {ipaddress.ip_network(x) for x in values}


class SharedHardGuardTests(unittest.TestCase):
    def sources(self):
        return {"service-broad": nets("198.51.100.0/24"),
                "service-exact": nets("203.0.113.7/32")}

    def hard(self):
        return [
            (ipaddress.ip_network("198.51.100.1/32"), {"antifilter-ip.lst"}),
            (ipaddress.ip_network("198.51.100.2/32"), {"v38-baseline-hard-or-unclassified"}),
            (ipaddress.ip_network("203.0.113.7/32"), {"antifilter-ip.lst"}),
        ]

    def test_new_hard_exception_warn_candidate(self):
        rows, summary = scan(
            self.hard(), nets("198.51.100.2/32"),
            nets("198.51.100.1/32", "203.0.113.7/32"),
            self.sources(), set(),
            nets("198.51.100.0/24", "203.0.113.0/24"), {}
        )
        self.assertEqual(summary["previously_untracked_prefixes"], ["198.51.100.1/32"])
        self.assertEqual(summary["shared_broad_service_hard_overrides"], 1)
        self.assertEqual(rows[0]["evidence_sources"], "antifilter-ip.lst")
        self.assertEqual(rows[0]["known_observation"], "NO")

    def test_approved_observation_marks_known_but_does_not_exempt(self):
        _, summary = scan(
            self.hard(), nets("198.51.100.2/32"),
            nets("198.51.100.1/32"), self.sources(), set(),
            nets("198.51.100.0/24"), {
                "198.51.100.1/32": "Observed only, no approval"
            }
        )
        self.assertEqual(summary["previously_untracked_hard_overrides"], 0)
        self.assertTrue(summary["baseline_observed_not_approved"])

    def test_hard_remaining_blocked_and_exact_host_not_flagged(self):
        rows, summary = scan(
            self.hard(), nets("198.51.100.1/32", "198.51.100.2/32"),
            nets("203.0.113.7/32"), self.sources(), set(),
            nets("198.51.100.0/24", "203.0.113.0/24"), {}
        )
        self.assertEqual(rows, [])
        self.assertEqual(summary["previously_untracked_hard_overrides"], 0)

    def test_baseline_requires_documented_host_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "baseline.tsv"
            p.write_text("prefix\tbasis\n198.51.100.0/24\ttoo wide\n")
            with self.assertRaisesRegex(ValueError, "exact IPv4"):
                load_observed_baseline(p)


if __name__ == "__main__":
    unittest.main()
