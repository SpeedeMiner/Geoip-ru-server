import unittest
from collect_v38_ripestat_rpki_validation import (
    collect_pairs,
    compare_status,
    normalize_ripestat_status,
    normalize_routeviews_status,
)


class RipestatRPKIValidationTests(unittest.TestCase):
    def test_collects_current_origins_from_all_three_exact_views(self):
        capture = {"summary": [
            {"source": "routeviews_exact_rib", "prefix": "5.45.215.0/24", "exact_origins": ["13238", "208398"]},
            {"source": "ripestat_routing_status", "prefix": "5.45.215.0/24", "exact_origins": ["AS208398", "212066"]},
            {"source": "ripestat_looking_glass_24h", "prefix": "5.45.215.0/24", "exact_origins": ["207304"]},
        ]}
        targets = [{"PREFIX": "5.45.215.0/24", "ARCHIVED_INVALID_ORIGINS": "AS208398|AS49505"}]
        self.assertEqual(collect_pairs(capture, targets), [
            ("5.45.215.0/24", "13238"),
            ("5.45.215.0/24", "207304"),
            ("5.45.215.0/24", "208398"),
            ("5.45.215.0/24", "212066"),
            ("5.45.215.0/24", "49505"),
        ])

    def test_routeviews_valid_and_invalid_are_preserved(self):
        self.assertEqual(normalize_routeviews_status("valid"), "valid")
        self.assertEqual(normalize_routeviews_status("invalid"), "invalid")
        self.assertEqual(normalize_routeviews_status("not-found"), "unknown")

    def test_ripe_invalid_variants_are_invalid_not_valid(self):
        self.assertEqual(normalize_ripestat_status("invalid_asn"), "invalid")
        self.assertEqual(normalize_ripestat_status("invalid_length"), "invalid")
        self.assertEqual(normalize_ripestat_status("valid"), "valid")
        self.assertEqual(normalize_ripestat_status("unknown"), "unknown")

    def test_valid_routeviews_vs_ripe_valid_matches(self):
        self.assertEqual(compare_status("valid", "valid"), "MATCH")

    def test_invalid_routeviews_vs_ripe_valid_is_explicit_disagreement(self):
        self.assertEqual(compare_status("invalid", "valid"), "STATUS_DISAGREEMENT")

    def test_not_found_vs_ripe_unknown_is_not_conflict(self):
        self.assertEqual(compare_status("not-found", "unknown"), "NO_DECISIVE_ROA_STATE")

    def test_unknown_is_not_valid(self):
        self.assertNotEqual(compare_status("unknown", "valid"), "MATCH")


if __name__ == "__main__":
    unittest.main()
