import ipaddress
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_vpn_route_candidates as build

class VpnRouteCandidateTests(unittest.TestCase):
    def test_global_and_private_address_handling(self):
        net, status = build.parse_net("1.1.1.0/24")
        self.assertEqual(str(net), "1.1.1.0/24")
        self.assertEqual(status, "ok")
        net, status = build.parse_net("10.1.2.3")
        self.assertIsNone(net)
        self.assertEqual(status, "non_global")

    def test_invalid_network(self):
        net, status = build.parse_net("not-a-network")
        self.assertIsNone(net)
        self.assertEqual(status, "invalid")

    def test_interval_difference_exact_address_count(self):
        source = build.intervals(
            [ipaddress.ip_network("10.0.0.0/24"), ipaddress.ip_network("10.0.1.0/24")], 4
        )
        baseline = build.intervals([ipaddress.ip_network("10.0.0.128/25")], 4)
        delta = build.subtract(source, baseline)
        self.assertEqual(build.size(delta), 384)
        rendered = [str(x) for x in build.interval_networks(delta, 4)]
        self.assertEqual(rendered, ["10.0.0.0/25", "10.0.1.0/24"])

    def test_interval_intersection(self):
        self.assertEqual(
            build.intersect([(0, 99), (200, 299)], [(50, 149), (250, 349)]),
            [(50, 99), (250, 299)],
        )

    def test_geoip_protobuf_ipv4_ipv6_roundtrip(self):
        original = {
            "ru_vpn_test": {
                ipaddress.ip_network("1.1.1.0/24"),
                ipaddress.ip_network("8.8.8.8/32"),
                ipaddress.ip_network("2001:4860::/32"),
            }
        }
        encoded = build.encode(original)
        parsed = build.parse_geoip(encoded)
        self.assertEqual(parsed["RU_VPN_TEST"], set(build.compact(original["ru_vpn_test"])))

    def test_candidate_category_does_not_create_ru(self):
        encoded = build.encode({"ru_vpn_new_vs_v37": [ipaddress.ip_network("1.1.1.0/24")]})
        parsed = build.parse_geoip(encoded)
        self.assertIn("RU_VPN_NEW_VS_V37", parsed)
        self.assertNotIn("RU", parsed)

    def test_amnezia_observations_keep_domain_and_cidr_types(self):
        payload = b'[{"hostname":"shop.example","ip":"1.2.3.4","ips":["1.2.3.5"]},{"hostname":"8.8.8.0/24","ip":"8.8.8.0/24"},{"hostname":"empty.example","ip":""}]'
        rows = build.parse_amnezia_observations("fixture", payload)
        self.assertEqual(rows[0]["hostname_type"], "domain")
        self.assertEqual(rows[0]["normalized_prefix"], "1.2.3.4/32")
        self.assertEqual(rows[2]["hostname_type"], "cidr")
        self.assertEqual(rows[2]["normalized_prefix"], "8.8.8.0/24")
        self.assertEqual(rows[3]["status"], "no_ip")

    def test_source_registry_contains_reverse_polarity_neither_as_direct(self):
        self.assertTrue(all(s["export"] is False for s in build.SOURCES if s["license"] == "UNDECLARED"))
        self.assertEqual(len({s["id"] for s in build.SOURCES}), len(build.SOURCES))

if __name__ == "__main__":
    unittest.main()
