import ipaddress
import unittest

from build_v41_overlay import (
    class_aware_effective_block_set,
    build_ru_service_protection_mask,
    intervals,
    normalize_interval_union,
)


def n(*ranges):
    return {ipaddress.ip_network(value) for value in ranges}


class V41PolicyIntegrationTests(unittest.TestCase):
    def test_union_normalizes_disjoint_unsorted_overlapping_masks(self):
        observed = normalize_interval_union(
            [(200, 299), (1000, 1200)],
            [(150, 250), (400, 499)],
            [(500, 600), (1201, 1250)],
        )
        self.assertEqual(observed, [(150, 299), (400, 600), (1000, 1250)])

    def test_core_company_survives_exact_and_resolved(self):
        exact = n("198.51.100.0/24")
        resolved = n("203.0.113.0/24")
        core = n("198.51.100.128/25", "203.0.113.128/25")
        result, _ = class_aware_effective_block_set(exact, resolved, core, set())
        self.assertEqual(result, n("198.51.100.0/25", "203.0.113.0/25"))

    def test_shared_and_rir_are_resolver_only_not_hard_exempt(self):
        exact = n("192.0.2.0/24", "198.51.100.0/24")
        resolved = n("192.0.2.0/24", "203.0.113.0/24")
        shared = n("192.0.2.0/24")
        regional = n("198.51.100.0/24", "203.0.113.128/25")
        result, _ = class_aware_effective_block_set(exact, resolved, set(), shared, regional)
        self.assertEqual(result, n("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/25"))

    def test_verified_service_exact_exception_is_preserved_from_v39(self):
        exact = n("77.88.5.5/32", "104.16.0.5/32")
        sources = {
            "kyoresuas-standard": n("77.88.0.0/18"),
            "hxehex-mobile-hosts": n("91.107.80.1/32"),
            "operator-whitelist": n("185.32.184.0/23"),
            "w1zardz-service-direct": n("85.192.10.0/24", "104.16.0.0/24"),
        }
        _, protected = build_ru_service_protection_mask(
            set(), rir_ru=n("85.192.0.0/16"), service_sources=sources
        )
        self.assertIn(ipaddress.ip_network("77.88.0.0/18"), protected)
        self.assertIn(ipaddress.ip_network("85.192.10.0/24"), protected)
        self.assertNotIn(ipaddress.ip_network("104.16.0.0/24"), protected)
        effective, _ = class_aware_effective_block_set(exact, set(), set(), set(), set(), protected)
        self.assertEqual(effective, n("104.16.0.5/32"))

    def test_ipv6_and_private_precedence_has_no_auto_promotion(self):
        exact = n("2001:db8:100::/48")
        core = n("2001:db8:100:8000::/49")
        output, _ = class_aware_effective_block_set(exact, set(), core, set())
        self.assertEqual(output, n("2001:db8:100::/49"))

    def test_legacy_unclassified_baseline_stays_hard_for_rir(self):
        exact = n("203.0.113.0/24")
        resolver = n("203.0.113.0/24")
        regional = n("203.0.113.0/24")
        output, only = class_aware_effective_block_set(exact, resolver, set(), set(), regional)
        self.assertEqual(output, exact)
        self.assertEqual(only, set())


if __name__ == "__main__":
    unittest.main()
