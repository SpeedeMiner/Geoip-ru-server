import ipaddress
import unittest

from audit_v41_service_hard_overrides import classify_override


def nets(*values):
    return {ipaddress.ip_network(value) for value in values}


class ServiceOverrideEvidenceTests(unittest.TestCase):
    def test_shared_hard_exception_from_broad_service(self):
        ip = ipaddress.ip_address("198.51.100.7")
        result = classify_override(
            ip,
            {"kyoresuas-standard": nets("198.51.100.0/24"), "hxehex-mobile-hosts": set()},
            core=set(),
            shared=nets("198.51.100.0/24"),
        )
        self.assertEqual(result["service_inputs"], "kyoresuas-standard")
        self.assertEqual(result["shared_prefix"], "198.51.100.0/24")
        self.assertTrue(result["shared_with_service_overlap"])
        self.assertTrue(result["broad_service_match"])
        self.assertEqual(result["decision"], "REVIEW_ONLY")

    def test_exact_service_host_does_not_count_as_broad(self):
        ip = ipaddress.ip_address("203.0.113.10")
        result = classify_override(
            ip, {"hxehex-mobile-hosts": nets("203.0.113.10/32")}, set(), set()
        )
        self.assertFalse(result["shared_with_service_overlap"])
        self.assertFalse(result["broad_service_match"])
        self.assertEqual(result["hxehex-mobile-hosts"], "203.0.113.10/32")

    def test_nested_service_masks_report_exact_and_broadest(self):
        ip = ipaddress.ip_address("192.0.2.50")
        result = classify_override(
            ip, {"operator-whitelist": nets("192.0.2.0/24", "192.0.2.48/28")},
            set(), set()
        )
        self.assertEqual(result["operator-whitelist"], "192.0.2.48/28")
        self.assertEqual(result["operator-whitelist_broadest"], "192.0.2.0/24")
        self.assertTrue(result["broad_service_match"])


if __name__ == "__main__":
    unittest.main()
