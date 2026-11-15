import ipaddress
import unittest

from build_v41_overlay import class_aware_effective_block_set, collapse


def nets(*values):
    return {ipaddress.ip_network(value) for value in values}


class CollapseIterableTests(unittest.TestCase):
    def test_one_shot_iterator_preserves_both_host_families(self):
        values = [ipaddress.ip_network("192.0.2.1/32"),
                  ipaddress.ip_network("2001:db8::1/128")]
        self.assertEqual(collapse(iter(values)), values)

    def test_iterables_have_same_canonical_result(self):
        cases = [
            ([], []),
            (["2001:db8::1/128"], ["2001:db8::1/128"]),
            (["192.0.2.1/32"], ["192.0.2.1/32"]),
            (["2001:db8::1/128", "192.0.2.1/32", "192.0.2.0/32",
              "192.0.2.1/32", "2001:db8::/128"],
             ["192.0.2.0/31", "2001:db8::/127"]),
        ]
        for source, expected in cases:
            for factory in (list, tuple, set, iter):
                with self.subTest(source=source, factory=factory.__name__):
                    values = [ipaddress.ip_network(value) for value in source]
                    self.assertEqual(collapse(factory(values)),
                                     [ipaddress.ip_network(value) for value in expected])


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


if __name__ == "__main__":
    unittest.main()
