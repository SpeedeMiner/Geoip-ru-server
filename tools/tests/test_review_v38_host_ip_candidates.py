import unittest

from tools.review_v38_host_ip_candidates import (
    canonical_ip,
    extract_rdap_holder,
    find_shared_flags,
    normalize_asn,
    rdap_server_for,
    route_objects_text,
)


class ReviewV38HostIpCandidateTests(unittest.TestCase):
    def test_ipv4_only_and_global(self):
        self.assertEqual(canonical_ip("3.5.120.169"), "3.5.120.169")
        for value in ("10.0.0.1", "192.168.1.1", "2001:db8::1", "8.8.8.8/32"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_ip(value)

    def test_normalize_asn(self):
        self.assertEqual(normalize_asn("16509"), "AS16509")
        self.assertEqual(normalize_asn("AS13335"), "AS13335")

    def test_shared_infrastructure_signal(self):
        flags = find_shared_flags(
            "AS16509=Amazon.com, Inc.",
            "Amazon Data Services",
            "kp-configs-smart-tv.s3.eu-central-1.amazonaws.com",
        )
        self.assertIn("AMAZON_AWS", flags)
        self.assertIn("SHARED_CLOUD_OR_CDN_HOSTNAME", flags)

    def test_domain_only_cloudfront_signal(self):
        flags = find_shared_flags("", "", "cdn.example.cloudfront.net")
        self.assertIn("SHARED_CLOUD_OR_CDN_HOSTNAME", flags)

    def test_route_object_formatting(self):
        text = route_objects_text([
            {"origin": 16509, "route_objects": [{"source": "RADB", "route": "3.5.120.0/22", "origin": "AS16509"}]},
            {"origin": 13335, "route_objects": []},
        ])
        self.assertIn("AS16509:RADB/3.5.120.0/22/AS16509", text)
        self.assertIn("AS13335:NO_EXACT_ROUTE_OBJECT", text)

    def test_rdap_longest_prefix_service(self):
        bootstrap = {"services": [
            [["0.0.0.0/0"], ["https://rdap.example/base/"]],
            [["3.5.0.0/16"], ["https://arin.example/rdap/"]],
            [["3.5.120.0/22"], ["https://more-specific.example/rdap/"]],
        ]}
        self.assertEqual(rdap_server_for("3.5.120.169", bootstrap), "https://more-specific.example/rdap/")

    def test_rdap_nested_vcard_holder(self):
        payload = {"name": "Network", "entities": [{"vcardArray": ["vcard", [["fn", {}, "text", "Registrant Example"]]]}]}
        holder = extract_rdap_holder(payload)
        self.assertIn("Network", holder)
        self.assertIn("Registrant Example", holder)


if __name__ == "__main__":
    unittest.main()
