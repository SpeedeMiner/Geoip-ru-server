import ipaddress
import tempfile
import unittest
from pathlib import Path

import build_v39_overlay as build


class GeoIPV39CorporateExemptionTests(unittest.TestCase):
    def test_company_exact_prefix_is_exempt_from_blocked_parent_only(self):
        direct = {ipaddress.ip_network("198.51.100.0/24")}
        blocked = {ipaddress.ip_network("198.51.100.0/24")}
        company = {ipaddress.ip_network("198.51.100.128/25")}

        effective_blocked = build.subtract_networks(blocked, company)
        final = build.subtract_networks(direct | company, set(), effective_blocked)

        self.assertEqual(build.addr_counts(effective_blocked), {"ipv4": 128, "ipv6": 0})
        self.assertEqual(build.addr_counts(final), {"ipv4": 128, "ipv6": 0})
        self.assertEqual(final, company)
        self.assertFalse(build.intersect(build.intervals(final, 4), build.intervals(effective_blocked, 4)))

    def test_private_still_wins_inside_company_exempt_prefix(self):
        direct = {ipaddress.ip_network("198.51.100.0/24")}
        blocked = {ipaddress.ip_network("198.51.100.0/24")}
        company = {ipaddress.ip_network("198.51.100.128/25")}
        private = {ipaddress.ip_network("198.51.100.192/26")}

        effective_blocked = build.subtract_networks(blocked, company)
        final = build.subtract_networks(direct | company, private, effective_blocked)

        self.assertEqual(build.addr_counts(final), {"ipv4": 64, "ipv6": 0})
        self.assertTrue(build.intersect(build.intervals(final, 4), build.intervals(company, 4)))
        self.assertFalse(build.intersect(build.intervals(final, 4), build.intervals(private, 4)))

    def test_ipv6_company_prefix_exception_is_exact(self):
        direct = {ipaddress.ip_network("2001:db8:100::/48")}
        blocked = {ipaddress.ip_network("2001:db8:100::/48")}
        company = {ipaddress.ip_network("2001:db8:100:8000::/49")}
        effective = build.subtract_networks(blocked, company)
        final = build.subtract_networks(direct | company, set(), effective)
        self.assertEqual(build.addr_counts(final)["ipv6"], 1 << 79)
        self.assertEqual(final, company)

    def test_no_company_overlap_means_original_block_policy_is_unchanged(self):
        blocked = {ipaddress.ip_network("203.0.113.0/24")}
        company = {ipaddress.ip_network("198.51.100.0/24")}
        self.assertEqual(build.subtract_networks(blocked, company), blocked)

    def test_company_sidecar_cidr_comments_are_parsed_as_prefixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "company-prefixes.txt"
            path.write_text(
                "# sha256=abc\n"
                "45.148.65.0/24 # AS212066[Yandex][STATIC-DIRECT]\n"
                "2001:db8:100::/48 # AS212066[Yandex]\n",
                encoding="utf-8",
            )
            parsed, stats = build.parse_cidr_file(path, allow_hosts=False)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(stats["valid_rows"], 2)
            self.assertEqual({n.version for n in parsed}, {4, 6})

    def test_ipsum_estimate_uses_company_exception_and_private_precedence(self):
        direct = {ipaddress.ip_network("203.0.113.0/24")}
        private = {ipaddress.ip_network("203.0.113.0/26")}
        blocked = {ipaddress.ip_network("203.0.113.64/26")}
        company = {ipaddress.ip_network("203.0.113.128/25")}
        blocked_effective = build.subtract_networks(blocked, company)
        ipsum_effective = build.subtract_networks(
            {ipaddress.ip_network("203.0.113.0/24")}, company
        )
        self.assertEqual(
            build.potential_ipsum_direct_overlap(direct | company, private, blocked_effective, ipsum_effective),
            {4: 0, 6: 0},
        )

    def test_protected_direct_mask_includes_curated_services_and_rir_ru_w1zardz_only(self):
        company = {ipaddress.ip_network("5.45.192.0/18")}
        rir_ru = {ipaddress.ip_network("85.192.0.0/16")}
        service_sources = {
            "kyoresuas-standard": {ipaddress.ip_network("77.88.0.0/18")},
            "hxehex-mobile-hosts": {ipaddress.ip_network("91.107.80.1/32")},
            "operator-whitelist": {ipaddress.ip_network("185.32.184.0/23")},
            "w1zardz-service-direct": {
                ipaddress.ip_network("85.192.10.0/24"),  # inside RIR-RU -> protected
                ipaddress.ip_network("104.16.0.0/24"),   # foreign CDN -> NOT protected from RKN carve
            },
        }
        protected, service_protected = build.build_protected_direct_mask(
            company, rir_ru=rir_ru, service_sources=service_sources
        )
        blocked = {
            ipaddress.ip_network("77.88.5.5/32"),
            ipaddress.ip_network("85.192.10.5/32"),
            ipaddress.ip_network("104.16.0.5/32"),
        }
        effective_blocked = build.subtract_networks(blocked, protected)
        self.assertIn(ipaddress.ip_network("85.192.10.0/24"), service_protected)
        self.assertNotIn(ipaddress.ip_network("104.16.0.0/24"), service_protected)
        self.assertEqual(effective_blocked, {ipaddress.ip_network("104.16.0.5/32")})


if __name__ == "__main__":
    unittest.main()
