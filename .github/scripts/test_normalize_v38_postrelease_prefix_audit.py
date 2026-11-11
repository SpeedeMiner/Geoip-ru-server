import unittest

from normalize_v38_postrelease_prefix_audit import canonical_status, compare_rpki_views


class StatusNormalizationTests(unittest.TestCase):
    def test_not_found_spelling_aliases(self):
        self.assertEqual(canonical_status("not-found"), canonical_status("notfound"))
        self.assertEqual(canonical_status("NOT_FOUND"), "not-found")

    def test_valid_and_invalid_remain_distinct(self):
        self.assertNotEqual(canonical_status("valid"), canonical_status("invalid"))

    def test_unknown_status_is_not_promoted(self):
        self.assertEqual(canonical_status("unknown"), "unknown")
        self.assertNotEqual(canonical_status("unknown"), canonical_status("valid"))

    def test_label_variant_is_not_semantic_conflict(self):
        result = compare_rpki_views({"20485": "not-found"}, {"20485": "notfound"})
        classification, conflicts, route_only, vrp_only, variants = result
        self.assertEqual(classification, "ORIGIN_SETS_AND_STATES_MATCH")
        self.assertEqual(conflicts, {})
        self.assertEqual(route_only, [])
        self.assertEqual(vrp_only, [])
        self.assertEqual(variants, {"20485": {
            "near_realtime_route_level": "not-found",
            "two_hour_aggregate_snapshot": "notfound",
        }})

    def test_real_invalid_valid_conflict_is_retained(self):
        result = compare_rpki_views({"208398": "invalid"}, {"208398": "valid"})
        classification, conflicts, _, _, variants = result
        self.assertEqual(classification, "SAME_ORIGIN_STATUS_DIFFERS")
        self.assertEqual(conflicts, {"208398": {
            "near_realtime_route_level": "invalid",
            "two_hour_aggregate_snapshot": "valid",
        }})
        self.assertEqual(variants, {})

    def test_origin_set_difference_is_not_hidden_by_matching_states(self):
        result = compare_rpki_views({"1": "valid", "2": "valid"}, {"1": "valid"})
        self.assertEqual(result[0], "ORIGIN_SET_DIFFERS")
        self.assertEqual(result[2], ["2"])

    def test_absent_route_is_not_treated_as_empty_agreement(self):
        self.assertEqual(compare_rpki_views({}, {})[0], "NO_EXACT_ROUTE")

    def test_missing_snapshot_is_separate(self):
        self.assertEqual(compare_rpki_views({"1": "valid"}, {})[0], "NO_TIMESTAMPED_VRP_STATE")


if __name__ == "__main__":
    unittest.main()
