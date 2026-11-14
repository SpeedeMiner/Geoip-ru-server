import unittest

from audit_v41_additional_geoip import additional_eligibility, category_allowed, resolver_only_loss


class AdditionalGeoIPAuditTests(unittest.TestCase):
    def test_grimbird_and_digne_are_one_group_and_asn_is_deduped(self):
        feeds = {
            "grimbird": [(1, 4)], "digne": [(1, 4)], "davoyan": [(3, 5)], "golukon": [(7, 9)],
            "v2fly": [(3, 3)], "loyalsoldier": [(12, 12)], "loyalsoldier-by": [(11, 11)],
        }
        masks = {"asn": [(4, 4), (9, 9)], "rir_ru": [(7, 8)], "private": [(8, 8)]}
        union, two_groups, eligible = additional_eligibility(feeds, masks)
        self.assertEqual(union, [(1, 5), (7, 9)])
        self.assertEqual(two_groups, [(3, 4)])
        self.assertEqual(eligible, [(7, 7)])

    def test_only_effective_resolver_loss_and_no_hard_private_or_admission(self):
        masks = {
            "resolver": [(1, 8)], "effective": [(1, 5), (8, 9)],
            "private": [(1, 1)], "hard": [(2, 2)], "admission": [(3, 3)], "direct": [(4, 4), (6, 7)],
        }
        self.assertEqual(resolver_only_loss([(1, 10)], masks), [(5, 5), (8, 8)])

    def test_non_geographic_categories_remain_outside_the_cohort(self):
        for source, accepted, excluded in (
            ("grimbird", ("RU", " ru-moscow "), ("ru-direct", "ru-wl-x", "ru-whitelist")),
            ("digne", ("ru", "ru-ip"), ("direct-ip", "whitelist")),
            ("davoyan", ("ru",), ("wl-ru",)),
            ("golukon", ("ru",), ("private",)),
        ):
            for tag in accepted:
                self.assertTrue(category_allowed(source, tag), (source, tag))
            for tag in excluded:
                self.assertFalse(category_allowed(source, tag), (source, tag))


if __name__ == "__main__":
    unittest.main()
