"""Address-enumeration oracle, independent of the production interval algorithms."""
import ipaddress
import random
import unittest

import build_v41_overlay as subject


def enumerate_ranges(ranges):
    return {address for first, last in ranges for address in range(first, last + 1)}


class IntervalOracleTests(unittest.TestCase):
    def test_small_windows_against_address_sets(self):
        rng = random.Random(4101)
        for version, origin in ((4, "192.0.2.0"), (6, "2001:db8::")):
            base = int(ipaddress.ip_address(origin))
            for trial in range(200):
                groups = []
                for _ in range(2):
                    pairs = [sorted(rng.sample(range(32), 2)) for _ in range(4)]
                    groups.append([(base + a, base + b) for a, b in pairs])
                left, right = groups
                expected_left, expected_right = map(enumerate_ranges, groups)
                a, b = map(subject.normalize_interval_union, groups)
                with self.subTest(version=version, trial=trial):
                    self.assertEqual(enumerate_ranges(subject.subtract(a, b)),
                                     expected_left - expected_right)
                    self.assertEqual(enumerate_ranges(subject.intersect(a, b)),
                                     expected_left & expected_right)
                    self.assertEqual(enumerate_ranges(subject.subtract_ranges(a, b)),
                                     expected_left - expected_right)
                    self.assertEqual(enumerate_ranges(subject.normalize_interval_union(left, right)),
                                     expected_left | expected_right)

    def test_large_ipv6_and_host_boundaries(self):
        cases = [
            (["2001:db8::/47"], ["2001:db8::/48"], ["2001:db8:1::/48"]),
            (["2001:db8::/126"], ["2001:db8::/128", "2001:db8::3/128"],
             ["2001:db8::1/128", "2001:db8::2/128"]),
            (["192.0.2.0/30"], ["192.0.2.0/32", "192.0.2.3/32"],
             ["192.0.2.1/32", "192.0.2.2/32"]),
            (["192.0.2.0/24"], ["192.0.2.128/25"], ["192.0.2.0/25"]),
            (["192.0.2.0/25"], ["192.0.2.128/25"], ["192.0.2.0/25"]),
            (["::/128", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128"],
             ["::/128"], ["ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128"]),
        ]
        for source, masks, expected in cases:
            with self.subTest(source=source, masks=masks):
                values = [set(map(ipaddress.ip_network, xs)) for xs in (source, masks, expected)]
                self.assertEqual(subject.subtract_networks(values[0], values[1]), values[2])


if __name__ == "__main__":
    unittest.main()
