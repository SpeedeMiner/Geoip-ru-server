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

    def test_hxehex_diagnostics_keep_source_rows_without_admitting_them(self):
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
            inputs.hxehex_ip.write_text("185.76.151.1\n185.76.150.1\n95.161.64.0/19\n")
            diagnostic, stats, rows = overlay.load_hxehex_diagnostics(inputs.hxehex_ip)
            self.assertEqual(diagnostic,
                             nets("185.76.151.1/32", "185.76.150.1/32", "95.161.64.0/19"))
            self.assertEqual(stats["role"], "diagnostic-only")
            self.assertEqual({row["category"] for row in rows}, {"diagnostic-only"})
            self.assertEqual({row["prefix"] for row in rows}, {str(net) for net in diagnostic})
            sources, service_stats, service_rows = overlay.load_service_inputs(inputs)
            self.assertNotIn("hxehex-mobile-hosts", sources)
            self.assertNotIn("hxehex-mobile-hosts", service_stats)
            self.assertTrue(all(row["source_id"] != "hxehex-mobile-hosts" for row in service_rows))
            self.assertFalse(diagnostic & set().union(*sources.values()))

    def test_feed_rejects_partial_or_noncanonical_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            feed = Path(folder) / "cidrs.txt"
            for bad in ("185.76.151.0/24\n", "185.76.151.1/24\n2a0a:f280::/32\n",
                        "0.0.0.0/0\n2a0a:f280::/32\n", "185.76.151.0/24\n" * 2 + "2a0a:f280::/32\n"):
                with self.subTest(data=bad):
                    feed.write_text(bad)
                    with self.assertRaises(ValueError):
                        read_telegram_feed(feed)
