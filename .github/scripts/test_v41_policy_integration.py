import ipaddress
import unittest

from build_v41_overlay import (
    class_aware_effective_block_set,
    build_service_protection_masks,
    addr_counts,
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

    def test_literal_hosts_survive_but_service_subnets_do_not_override_hard(self):
        exact = n("77.88.5.5/32", "77.88.5.6/32", "77.88.5.7/32",
                  "104.16.0.5/32", "185.32.184.6/32", "2001:db8::5/128",
                  "2001:db8::6/128")
        resolved = n("77.88.5.8/32", "185.32.184.7/32", "2001:db8::7/128")
        sources = {
            "kyoresuas-standard": n("77.88.0.0/18", "77.88.5.6/32", "77.88.5.7/32", "2001:db8::/48"),
            "hxehex-mobile-hosts": n("2001:db8::6/128"),
            "operator-whitelist": n("185.32.184.0/23", "185.32.184.6/32"),
            "w1zardz-service-direct": n("104.16.0.0/24"),
        }
        hosts, resolver = build_service_protection_masks({"RU": set(), "BY": set(), "KZ": set()}, sources)
        self.assertEqual(hosts, n("77.88.5.6/32", "77.88.5.7/32", "2001:db8::6/128"))
        effective, _ = class_aware_effective_block_set(
            exact, resolved, set(), n("77.88.0.0/18"), set(), hosts, resolver,
        )
        self.assertEqual(effective, n("77.88.5.5/32", "104.16.0.5/32",
                                      "185.32.184.6/32", "2001:db8::5/128"))

    def test_w1zardz_regional_intersection_cannot_synthesize_a_hard_exception(self):
        hosts, resolver = build_service_protection_masks(
            {"RU": n("192.0.2.1/32", "192.0.2.4/31"),
             "BY": n("198.51.100.1/32"), "KZ": n("2001:db8::1/128")},
            {"w1zardz-service-direct": n("192.0.2.0/30", "192.0.2.4/32", "192.0.2.5/32",
                                         "198.51.100.1/32", "2001:db8::/64")},
        )
        self.assertEqual(hosts, n("192.0.2.4/32", "192.0.2.5/32"))
        self.assertEqual(addr_counts(resolver), {"ipv4": 4, "ipv6": 1})
        exact = n("192.0.2.1/32", "198.51.100.1/32")
        effective, _ = class_aware_effective_block_set(
            exact, n("2001:db8::1/128"), set(), set(), set(), hosts, resolver,
        )
        self.assertEqual(effective, exact)

    def test_subnet_cannot_be_passed_as_hard_service_exception(self):
        with self.assertRaisesRegex(ValueError, "literal host"):
            class_aware_effective_block_set(
                set(), set(), set(), set(), service_exact_hosts=n("192.0.2.0/31"),
            )

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
