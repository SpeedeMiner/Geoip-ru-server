import ipaddress
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import build_v41_overlay as overlay
from validate_v41_telegram import PINNED_FEED, assert_disjoint, read_telegram_feed


def nets(*items):
    return {ipaddress.ip_network(x) for x in items}


class TelegramPrecedenceTests(unittest.TestCase):
    def test_independent_gate_checks_every_prefix(self):
        feed = read_telegram_feed(PINNED_FEED)
        self.assertEqual({v: sum(n.version == v for n in feed) for v in (4, 6)}, {4: 9, 6: 5})
        with tempfile.TemporaryDirectory() as folder:
            dat = Path(folder) / "candidate.dat"
            baseline = nets("1.2.3.4/32", "2001:4860::1/128")
            for prefix in sorted(feed, key=lambda n: (n.version, int(n.network_address))):
                host = ipaddress.ip_network((prefix.network_address + 1, prefix.max_prefixlen))
                with self.subTest(prefix=prefix):
                    dat.write_bytes(overlay.encode_geoip(
                        {"RU": baseline | {host}, "PRIVATE": nets("10.0.0.0/8")}))
                    with self.assertRaisesRegex(ValueError, "RU intersects official Telegram prefix"):
                        assert_disjoint(dat, feed)
            dat.write_bytes(overlay.encode_geoip(
                {"RU": baseline, "PRIVATE": nets("10.0.0.0/8")}))
            assert_disjoint(dat, feed)

    def test_gate_detects_containing_prefix_and_the_reported_host(self):
        feed = read_telegram_feed(PINNED_FEED)
        with tempfile.TemporaryDirectory() as folder:
            dat = Path(folder) / "candidate.dat"
            for route in ("185.76.151.1/32", "185.76.150.0/23"):
                with self.subTest(route=route):
                    dat.write_bytes(overlay.encode_geoip(
                        {"RU": nets(route, "2001:4860::1/128"), "PRIVATE": nets("10.0.0.0/8")}))
                    with self.assertRaisesRegex(ValueError, r"185\.76\.151\.0/24"):
                        assert_disjoint(dat, feed)

    def test_official_feed_wins_over_core_and_service_exceptions(self):
        hard = nets("185.76.151.0/24")
        protected = nets("185.76.151.1/32", "1.2.3.4/32")
        v6 = nets("2a0a:f280::1/128")
        effective, resolver_only = overlay.class_aware_effective_block_set(
            hard, v6 | nets("1.2.3.4/32"), v6, set(), service_exact_hosts=protected,
            non_exempt=read_telegram_feed(PINNED_FEED))
        self.assertEqual(overlay.subtract_networks(protected | v6, effective), nets("1.2.3.4/32"))
        self.assertEqual(resolver_only, nets("1.2.3.4/32"))

    def test_hxehex_source_filters_official_and_curated_rows_without_splitting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs = SimpleNamespace()
            for name in ("kyoresuas_services", "kyoresuas_v4", "kyoresuas_v6", "hxehex_ip",
                         "w1zardz", "escapingworm"):
                p = root / name
                p.write_text("2001:4860::1/128\n" if name == "kyoresuas_v6" else "1.2.3.4/32\n")
                setattr(inputs, name, p)
            inputs.kyoresuas_services.write_text(json.dumps({"categories": [{"services": [
                {"tier": "lite", "ipv4": ["1.2.3.4/32"]} for _ in range(50)]}]}))
            inputs.hxehex_ip.write_text(
                "185.76.151.1\n185.76.150.1\n95.161.64.1\n"
                "95.161.64.0/21\n95.161.64.0/20\n95.161.64.0/19\n95.161.80.1\n"
            )
            sources, stats, rows = overlay.load_service_inputs(inputs)
            self.assertEqual(sources["hxehex-mobile-hosts"],
                             nets("185.76.150.1/32", "95.161.64.0/19", "95.161.80.1/32"))
            self.assertEqual(stats["hxehex-mobile-hosts"]["telegram_unique_prefixes_rejected"], 4)
            self.assertEqual({row["prefix"] for row in rows if row["source_id"] == "hxehex-mobile-hosts"},
                             {"185.76.150.1/32", "95.161.64.0/19", "95.161.80.1/32"})
            regions = {country: set() for country in ("RU", "BY", "KZ")}
            exact, resolver = overlay.build_service_protection_masks(regions, sources)
            self.assertNotIn(ipaddress.ip_network("95.161.64.1/32"), exact)
            hard = nets("95.161.64.0/20")
            effective, _ = overlay.class_aware_effective_block_set(
                hard, set(), set(), set(), service_exact_hosts=exact,
                service_resolver_prefixes=resolver, non_exempt=read_telegram_feed(PINNED_FEED),
            )
            self.assertEqual(overlay.subtract_networks(sources["hxehex-mobile-hosts"], effective),
                             nets("185.76.150.1/32", "95.161.80.0/20"))

    def test_feed_rejects_partial_or_noncanonical_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            feed = Path(folder) / "cidrs.txt"
            for bad in ("185.76.151.0/24\n", "185.76.151.1/24\n2a0a:f280::/32\n",
                        "0.0.0.0/0\n2a0a:f280::/32\n", "185.76.151.0/24\n" * 2 + "2a0a:f280::/32\n"):
                with self.subTest(data=bad):
                    feed.write_text(bad)
                    with self.assertRaises(ValueError):
                        read_telegram_feed(feed)
