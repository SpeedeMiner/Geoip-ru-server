import ipaddress
import unittest

from audit_v41_all_hard_override_classes import partition_overrides


def nets(*items):
    return {ipaddress.ip_network(x, strict=True) for x in items}


class AllHardOverrideClassTests(unittest.TestCase):
    def test_precedence_and_exact_accounting(self):
        hard = [(ipaddress.ip_network(x), {"antifilter-ip.lst"}) for x in (
            "192.0.2.1/32", "192.0.2.2/32", "192.0.2.3/32", "192.0.2.4/32")]
        result = partition_overrides(nets("192.0.2.0/24"), hard, set(),
            core=nets("192.0.2.0/31"),
            shared=nets("192.0.2.0/30"),
            service_sources={"service": nets("192.0.2.2/31")})
        v = result[4]
        self.assertEqual(v["total_addresses"], 4)
        self.assertEqual(v["by_origin_class"]["CORE_CORPORATE"]["addresses"], 1)
        self.assertEqual(v["by_origin_class"]["SHARED_INFRA"]["addresses"], 2)
        self.assertEqual(v["by_origin_class"]["OTHER"]["addresses"], 1)
        self.assertEqual(v["by_origin_class"]["SHARED_INFRA"]["also_verified_service_addresses"], 2)
        self.assertEqual(v["by_origin_class"]["OTHER"]["without_verified_service_addresses"], 1)

    def test_ipv6_as_well(self):
        hard = [(ipaddress.ip_network("2001:db8::2/128"), {"legacy"})]
        result = partition_overrides(nets("2001:db8::/126"), hard, set(), set(),
            set(), {"service": nets("2001:db8::/126")})
        self.assertEqual(result[6]["total_addresses"], 1)
        self.assertEqual(result[4]["total_addresses"], 0)

    def test_effective_block_intersection_is_fatal(self):
        host = nets("192.0.2.5/32")
        with self.assertRaisesRegex(ValueError, "overlap"):
            partition_overrides(host, [(next(iter(host)), {"hard"})], host,
                                set(), set(), {"service": set()})


if __name__ == "__main__":
    unittest.main()
