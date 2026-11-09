import contextlib
import io
import ipaddress
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prepare_blocked_sources import TELEGRAM_PREFIXES, is_host, main, parse_line, subnet_auto_approved


class BlockedSourcePolicyTests(unittest.TestCase):
    def test_ip_resolve_host_semantics(self):
        self.assertTrue(is_host(parse_line("203.0.113.9")))
        self.assertTrue(is_host(parse_line("2001:db8::1")))
        self.assertFalse(is_host(parse_line("203.0.113.0/24")))

    def test_subnet_threshold_is_conservative(self):
        self.assertTrue(subnet_auto_approved(ipaddress.ip_network("198.51.100.0/24")))
        self.assertTrue(subnet_auto_approved(ipaddress.ip_network("2001:db8:1::/112")))
        self.assertFalse(subnet_auto_approved(ipaddress.ip_network("2001:db8:1::/48")))
        self.assertTrue(subnet_auto_approved(ipaddress.ip_network("10.0.0.0/16")))
        self.assertFalse(subnet_auto_approved(ipaddress.ip_network("10.0.0.0/15")))
        self.assertFalse(subnet_auto_approved(ipaddress.ip_network("2001:db8::/111")))

    def test_telegram_explicit_wide_prefixes_are_curated(self):
        self.assertIn("149.154.160.0/20", TELEGRAM_PREFIXES)
        self.assertIn("2a0a:f280::/32", TELEGRAM_PREFIXES)

    def test_strict_cidr_parsing(self):
        self.assertEqual(str(parse_line("IP-CIDR, 192.0.2.0/24,no-resolve")), "192.0.2.0/24")
        self.assertEqual(str(parse_line("2001:db8::1")), "2001:db8::1/128")
        with self.assertRaises(ValueError):
            parse_line("192.0.2.1/24")

    def test_end_to_end_sources_are_classified_conservatively(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {name: root / name for name in (
                "ip.lst", "ipresolve.lst", "subnet.lst", "community.lst", "ipsum.lst",
                "approved.txt", "review.tsv", "stats.tsv", "checksums.sha256",
            )}

            # Generate >1,000 exact host addresses for each required host-IP source.
            start = int(ipaddress.ip_address("198.51.0.1"))
            paths["ip.lst"].write_text(
                "\n".join(str(ipaddress.ip_address(start + i)) for i in range(1005)) + "\n",
                encoding="utf-8",
            )
            start_v6 = int(ipaddress.ip_address("2001:db8:100::1"))
            paths["ipresolve.lst"].write_text(
                "\n".join(str(ipaddress.ip_address(start_v6 + i)) for i in range(1005)) + "\n",
                encoding="utf-8",
            )
            paths["subnet.lst"].write_text(
                "203.0.113.0/24\n192.0.0.0/8\n2001:db8:1::/112\n2001:db8:2::/48\n", encoding="utf-8"
            )
            paths["community.lst"].write_text(
                "192.0.2.123\n", encoding="utf-8"
            )
            paths["ipsum.lst"].write_text(
                "203.0.113.0/24\n", encoding="utf-8"
            )

            argv = [
                "prepare_blocked_sources.py",
                "--ip-list", str(paths["ip.lst"]),
                "--ipresolve", str(paths["ipresolve.lst"]),
                "--subnet", str(paths["subnet.lst"]),
                "--community", str(paths["community.lst"]),
                "--refilter", str(paths["ipsum.lst"]),
                "--approved", str(paths["approved.txt"]),
                "--review", str(paths["review.tsv"]),
                "--stats", str(paths["stats.tsv"]),
                "--checksums", str(paths["checksums.sha256"]),
            ]
            with mock.patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)

            approved = paths["approved.txt"].read_text(encoding="utf-8")
            review = paths["review.tsv"].read_text(encoding="utf-8")
            stats = paths["stats.tsv"].read_text(encoding="utf-8")

            self.assertIn("198.51.0.1/32", approved)
            self.assertIn("2001:db8:100::1/128", approved)
            self.assertIn("203.0.113.0/24", approved)
            self.assertIn("2001:db8:1::/112", approved)
            self.assertIn("149.154.160.0/20", approved)
            self.assertNotIn("192.0.0.0/8", approved)
            self.assertNotIn("2001:db8:2::/48", approved)
            self.assertNotIn("192.0.2.123/32", approved)
            self.assertIn("192.0.0.0/8", review)
            self.assertIn("2001:db8:2::/48", review)
            self.assertIn("192.0.2.123/32", review)
            self.assertIn("community-antifilter-community.lst", stats)
            self.assertIn("re-filter-ipsum.lst", stats)


if __name__ == "__main__":
    unittest.main()
