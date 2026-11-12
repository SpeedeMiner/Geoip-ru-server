import unittest

from audit_v41_current_hard_ris import annotate, normalize_ris


class CurrentHardRISEvidenceTests(unittest.TestCase):
    def test_known_route(self):
        actual = normalize_ris("158.160.63.17", {
            "status": "ok", "data": {"prefix": "158.160.0.0/16", "asns": [200350]}
        })
        self.assertEqual(actual["ris_status"], "OBSERVED")
        self.assertEqual(actual["ris_asns"], "AS200350")

    def test_unrelated_prefix_is_not_valid_evidence(self):
        actual = normalize_ris("158.160.63.17", {
            "status": "ok", "data": {"prefix": "192.0.2.0/24", "asns": [64501]}
        })
        self.assertEqual(actual["ris_status"], "UNKNOWN")

    def test_unobserved_route_does_not_prove_unroutable(self):
        actual = normalize_ris("192.0.2.1", {
            "status": "ok", "data": {"prefix": None, "asns": []}
        })
        self.assertEqual(actual["ris_status"], "NOT_OBSERVED")

    def test_scan_only_current_hard_and_never_changes_routing(self):
        rows = [
            {"prefix": "192.0.2.1/32", "evidence_sources": "antifilter-ip.lst,v38-baseline-hard-or-unclassified"},
            {"prefix": "192.0.2.2/32", "evidence_sources": "v38-baseline-hard-or-unclassified"},
        ]
        result, summary = annotate(rows, lambda _: {
            "status": "ok", "data": {"prefix": "192.0.2.0/24", "asns": [64500]}
        }, sleep_seconds=0)
        self.assertEqual(len(result), 1)
        self.assertEqual(summary["ris_observed"], 1)
        self.assertEqual(result[0]["actual_rkn_block_verified"], "NO")
        self.assertEqual(result[0]["action"], "AUDIT_ONLY")

    def test_failed_external_lookup_is_unknown(self):
        def fail(_):
            raise TimeoutError("not reachable")
        records, summary = annotate([
            {"prefix": "192.0.2.5/32", "evidence_sources": "antifilter-ip.lst"}
        ], fail, sleep_seconds=0)
        self.assertEqual(records[0]["ris_status"], "UNKNOWN")
        self.assertEqual(summary["ris_unknown"], 1)


if __name__ == "__main__":
    unittest.main()
