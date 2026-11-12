import ipaddress
import unittest

from build_v41_overlay import class_aware_effective_block_set


def nets(*values):
    return {ipaddress.ip_network(value) for value in values}


class ClassAwareBlockPrecedenceTests(unittest.TestCase):
    def test_core_corporate_is_exempt_from_exact_and_resolver_blocks(self):
        exact = nets("198.51.100.0/24")
        resolved = nets("203.0.113.0/24")
        core = nets("198.51.100.128/25", "203.0.113.128/25")
        shared = set()
        effective, resolver_only = class_aware_effective_block_set(exact, resolved, core, shared)
        self.assertEqual(effective, nets("198.51.100.0/25", "203.0.113.0/25"))
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

    def test_unclassified_legacy_baseline_remains_hard_for_shared_infrastructure(self):
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


if __name__ == "__main__":
    unittest.main()
