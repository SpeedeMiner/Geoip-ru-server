import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_v41_overlay import (build_light_overlay, class_aware_effective_block_set,
                               encode_geoip, parse_geoip_dat, subtract_networks, write_light_output)


def nets(*values):
    return {ipaddress.ip_network(value) for value in values}


class ClassAwareBlockPrecedenceTests(unittest.TestCase):
    def test_core_corporate_is_exempt_from_resolver_but_not_hard_ip_evidence(self):
        exact = nets("198.51.100.0/24")
        resolved = nets("203.0.113.0/24")
        core = nets("198.51.100.128/25", "203.0.113.128/25")
        shared = set()
        effective, resolver_only = class_aware_effective_block_set(exact, resolved, core, shared)
        self.assertEqual(effective, nets("198.51.100.0/24", "203.0.113.0/25"))
        self.assertEqual(resolver_only, resolved)

    def test_shared_infrastructure_is_exempt_only_from_resolver_only_entries(self):
        exact = nets("198.51.100.0/24")
        resolved = nets("203.0.113.0/24")
        shared = nets("203.0.113.128/25")
        effective, resolver_only = class_aware_effective_block_set(exact, resolved, set(), shared)
        self.assertEqual(effective, nets("198.51.100.0/24", "203.0.113.0/25"))
        self.assertEqual(resolver_only, resolved)

    def test_exact_block_wins_when_same_ip_is_also_in_ipresolve(self):
        exact = nets("203.0.113.0/24")
        resolved = nets("203.0.113.0/24")
        shared = nets("203.0.113.0/24")
        effective, resolver_only = class_aware_effective_block_set(exact, resolved, set(), shared)
        self.assertEqual(effective, exact)
        self.assertEqual(resolver_only, set())

    def test_explicit_subnet_remains_hard_for_shared_infrastructure(self):
        legacy = nets("192.0.2.0/24")
        current_resolved = nets("203.0.113.0/24")
        shared = nets("192.0.2.0/24", "203.0.113.0/24")
        effective, resolver_only = class_aware_effective_block_set(legacy, current_resolved, set(), shared)
        self.assertEqual(effective, legacy)
        self.assertEqual(resolver_only, current_resolved)

    def test_overlapping_class_masks_fail_closed(self):
        shared = nets("198.51.100.0/24")
        with self.assertRaises(ValueError):
            class_aware_effective_block_set(set(), set(), shared, shared)


class LightOverlayTests(unittest.TestCase):
    def test_only_optional_hosts_after_policy_are_removed(self):
        core = nets("192.0.2.0/29", "198.51.100.9/32", "2001:db8:1::1/128")
        optional = nets("192.0.2.2/32", "192.0.2.4/30", "198.51.100.9/32",
                        "198.51.100.17/32", "198.51.100.30/32", "198.51.100.31/32",
                        "203.0.113.0/30", "2001:db8:1::1/128", "2001:db8:2::1/128")
        private = nets("10.0.0.0/8", "fc00::/7")
        excluded = nets("192.0.2.2/32", "203.0.113.0/31", "203.0.113.2/32")
        full = subtract_networks(core | optional, private, excluded)
        light, removed = build_light_overlay(full, core, optional, private, excluded)
        self.assertEqual(removed, {"ipv4": 2, "ipv6": 1})
        self.assertEqual(light, subtract_networks(full, nets("198.51.100.17/32",
                                                            "203.0.113.3/32", "2001:db8:2::1/128")))
        self.assertFalse(subtract_networks(subtract_networks(core, excluded), light))
        self.assertFalse(subtract_networks(light, full))
        self.assertIn(ipaddress.ip_network("198.51.100.30/31"), light)
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "geoip_RU_light.dat"
            result = write_light_output(out, encode_geoip({"RU": full, "PRIVATE": private}),
                                        full, core, optional, private, excluded)
            self.assertEqual(parse_geoip_dat(out), {"RU": light, "PRIVATE": private})
            self.assertEqual(out.with_suffix(".dat.sha256sum").read_text(),
                             f"{result['sha256']}  {out.name}\n")

    def test_unattributed_full_address_fails_instead_of_silently_dropping_it(self):
        with self.assertRaisesRegex(ValueError, "source partition"):
            build_light_overlay(nets("198.51.100.1/32"), set(), set(), set(), set())


if __name__ == "__main__":
    unittest.main()
