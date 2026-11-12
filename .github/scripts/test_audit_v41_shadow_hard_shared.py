import ipaddress
import unittest
from audit_v41_shadow_hard_shared import calculate

def nets(*values):
    return {ipaddress.ip_network(x) for x in values}

class ShadowHardWithinSharedTests(unittest.TestCase):
    def test_exact_and_wide_hard_intersection(self):
        ru = nets("192.0.2.0/24", "198.51.100.0/24")
        shared = nets("192.0.2.0/24", "198.51.100.0/24")
        hard = [
            (ipaddress.ip_network("192.0.2.1/32"), {"antifilter-ip.lst"}),
            (ipaddress.ip_network("198.51.100.0/25"), {"antifilter-subnet.lst"}),
        ]
        result, overlaps = calculate(ru, hard, shared, set())
        self.assertEqual(result["ipv4"]["eligible_v41_direct_hard_shared_addresses"], 129)
        self.assertEqual(result["ipv4"]["of_which_current_ip_lst_addresses"], 1)
        self.assertEqual(result["ipv4"]["eligible_v41_direct_hard_shared_cidrs"], 2)
        self.assertEqual(result["ipv6"]["eligible_v41_direct_hard_shared_addresses"], 0)

    def test_effective_overlap_is_inconsistent(self):
        with self.assertRaisesRegex(ValueError, "intersects effective"):
            calculate(nets("192.0.2.1/32"),
                      [(ipaddress.ip_network("192.0.2.1/32"), {"antifilter-ip.lst"})],
                      nets("192.0.2.0/24"), nets("192.0.2.1/32"))

    def test_outside_shared_is_not_counted(self):
        result, _ = calculate(
            nets("192.0.2.1/32"),
            [(ipaddress.ip_network("192.0.2.1/32"), {"antifilter-ip.lst"})],
            nets("198.51.100.0/24"), set())
        self.assertEqual(result["ipv4"]["eligible_v41_direct_hard_shared_addresses"], 0)

if __name__ == "__main__":
    unittest.main()
