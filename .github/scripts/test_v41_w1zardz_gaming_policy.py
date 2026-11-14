import ipaddress
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import build_v41_overlay as overlay
from validate_v41_overlay import assert_no_w1zardz_only_gaming_routes
from validate_v41_release_gate import literal_service_exceptions


def nets(*items):
    return {ipaddress.ip_network(x) for x in items}


class W1ZARDZGamingPolicyTests(unittest.TestCase):
    def test_reviewed_table_covers_seven_cidrs_and_262_addresses(self):
        excluded = overlay.read_w1zardz_exclusions(overlay.W1ZARDZ_EXCLUSIONS)
        self.assertEqual(excluded, nets(
            "38.244.136.0/24", "104.26.6.129/32", "104.26.7.129/32",
            "143.20.177.3/32", "172.64.150.18/32", "172.67.73.25/32", "172.67.73.142/32"))
        self.assertEqual(overlay.addr_counts(excluded), {"ipv4": 262, "ipv6": 0})

    def test_strict_exclusions_and_missing_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exclusions.txt"
            with self.assertRaises(FileNotFoundError):
                overlay.read_w1zardz_exclusions(path)
            for text in ("", "38.244.136.1/24", "38.244.136.0/23", "38.244.136.5",
                         "2001:4860::1/128", "38.244.136.0/24\n38.244.136.0/24"):
                with self.subTest(text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        overlay.read_w1zardz_exclusions(path)

    def test_supernets_are_trimmed_without_losing_adjacent_coverage(self):
        before = nets("38.244.136.0/23", "104.26.6.128/31", "2001:4860::1/128")
        excluded = nets("38.244.136.0/24", "104.26.6.129/32")
        kept, removed = overlay.filter_w1zardz_routes(before, excluded)
        self.assertEqual(kept, nets("38.244.137.0/24", "104.26.6.128/32", "2001:4860::1/128"))
        self.assertEqual(removed, excluded)
        self.assertEqual(overlay.filter_w1zardz_routes(kept, excluded), (kept, set()))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "w1zardz"
            path.write_text("\n".join(map(str, before)))
            literal = overlay.original_w1zardz_hosts(path, kept)
        self.assertEqual(literal, nets("2001:4860::1/128"))
        regions = {"RU": nets("104.26.6.0/24"), "BY": set(), "KZ": set()}
        sources = {"w1zardz-service-direct": kept}
        exact, resolver = overlay.build_service_protection_masks(regions, sources, w1zardz_literal_hosts=literal)
        self.assertEqual(exact, set())
        self.assertEqual(resolver, nets("104.26.6.128/32"))
        self.assertEqual(literal_service_exceptions(regions, sources, w1zardz_literal_hosts=literal), set())

    def test_load_service_scope_and_secondary_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = SimpleNamespace(**{key: root / key for key in (
                "kyoresuas_services", "kyoresuas_v4", "kyoresuas_v6", "w1zardz", "escapingworm")})
            inputs.kyoresuas_v4.write_text("104.26.6.129/32\n")
            inputs.kyoresuas_v6.write_text("2001:4860::1/128\n")
            inputs.kyoresuas_services.write_text(json.dumps({"categories": [{"services": [
                {"tier": "lite", "ipv4": ["1.2.3.4/32"]} for _ in range(50)]}]}))
            inputs.w1zardz.write_text("104.26.6.129/32\n38.244.136.0/24\n1.2.3.5/32\n")
            inputs.escapingworm.write_text("1.2.3.6/32\n")
            sources, stats, provenance = overlay.load_service_inputs(inputs)
            self.assertEqual(sources["w1zardz-service-direct"], nets("1.2.3.5/32"))
            self.assertEqual(stats["w1zardz-service-direct"]["excluded_ipv4_addresses"], 257)
            self.assertEqual({r["prefix"] for r in provenance if r["category"] == "excluded-game-ip"},
                             {"104.26.6.129/32", "38.244.136.0/24"})
            supported = overlay.union_networks(*sources.values())
            assert_no_w1zardz_only_gaming_routes(supported, supported, nets("104.26.6.129/32", "38.244.136.0/24"))
            with self.assertRaisesRegex(ValueError, "W1ZARDZ-only gaming"):
                assert_no_w1zardz_only_gaming_routes(
                    supported | nets("38.244.136.42/32"), supported, nets("38.244.136.0/24"))


if __name__ == "__main__":
    unittest.main()
