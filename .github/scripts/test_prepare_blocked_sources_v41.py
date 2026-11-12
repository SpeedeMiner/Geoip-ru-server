import contextlib
import io
import ipaddress
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prepare_blocked_sources_v41 import TELEGRAM_PREFIXES, is_host, main, parse_line, subnet_auto_approved


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
                "ip.lst", "ipresolve.lst", "subnet.lst", "community.lst", "ipsum.lst", "baseline.txt", "exact.txt", "resolved.txt",
                "approved.txt", "review.tsv", "stats.tsv", "checksums.sha256",
            )}

            # Generate >1,000 exact host addresses for each required host-IP source.
            start = int(ipaddress.ip_address("198.51.0.1"))
            paths["ip.lst"].write_text(
                "\n".join(str(ipaddress.ip_address(start + i)) for i in range(1005)) + "\n",
                encoding="utf-8",
            )
            # Current ipresolve endpoint is an empty response. The pinned v38
            # approved baseline carries forward its previously approved addresses.
            paths["ipresolve.lst"].write_text("", encoding="utf-8")
            start_baseline = int(ipaddress.ip_address("192.0.10.1"))
            baseline_hosts = [str(ipaddress.ip_address(start_baseline + i)) for i in range(1005)]
            baseline_hosts.append("2001:db8:100::1")
            paths["baseline.txt"].write_text("\n".join(baseline_hosts) + "\n", encoding="utf-8")
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
                "prepare_blocked_sources_v41.py",
                "--ip-list", str(paths["ip.lst"]),
                "--ipresolve", str(paths["ipresolve.lst"]),
                "--baseline", str(paths["baseline.txt"]),
                "--subnet", str(paths["subnet.lst"]),
                "--community", str(paths["community.lst"]),
                "--refilter", str(paths["ipsum.lst"]),
                "--approved", str(paths["approved.txt"]),
                "--exact-approved", str(paths["exact.txt"]),
                "--resolved-approved", str(paths["resolved.txt"]),
                "--review", str(paths["review.tsv"]),
                "--stats", str(paths["stats.tsv"]),
                "--checksums", str(paths["checksums.sha256"]),
            ]
            with mock.patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)

            approved = paths["approved.txt"].read_text(encoding="utf-8")
            review = paths["review.tsv"].read_text(encoding="utf-8")
            stats = paths["stats.tsv"].read_text(encoding="utf-8")
            exact = paths["exact.txt"].read_text(encoding="utf-8")
            resolved = paths["resolved.txt"].read_text(encoding="utf-8")

            self.assertIn("198.51.0.1/32", approved)
            self.assertIn("2001:db8:100::1/128", approved)
            self.assertIn("192.0.10.1/32", approved)
            self.assertIn("EMPTY_FALLBACK_V38_PINNED_BASELINE", stats)
            self.assertIn("v38-approved-baseline", stats)
            self.assertIn("192.0.10.1/32", exact)
            self.assertIn("198.51.0.1/32", exact)
            self.assertNotIn("192.0.10.1/32", resolved)
            self.assertEqual(len([x for x in resolved.splitlines() if x and not x.startswith("#")]), 0)
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

    def test_pinned_baseline_rejects_unapproved_wide_prefixes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.txt"
            start = int(ipaddress.ip_address("198.18.0.1"))
            hosts = [str(ipaddress.ip_address(start + i)) for i in range(1005)]
            baseline.write_text("\n".join(hosts + ["192.0.0.0/8"]) + "\n", encoding="utf-8")
            for name in ("ip.lst", "ipresolve.lst", "subnet.lst", "community.lst", "ipsum.lst"):
                (root / name).write_text("", encoding="utf-8")
            argv = [
                "prepare_blocked_sources_v41.py",
                "--ip-list", str(root / "ip.lst"),
                "--ipresolve", str(root / "ipresolve.lst"),
                "--baseline", str(baseline),
                "--subnet", str(root / "subnet.lst"),
                "--community", str(root / "community.lst"),
                "--refilter", str(root / "ipsum.lst"),
                "--approved", str(root / "approved.txt"),
                "--exact-approved", str(root / "exact.txt"),
                "--resolved-approved", str(root / "resolved.txt"),
                "--review", str(root / "review.tsv"),
                "--stats", str(root / "stats.tsv"),
                "--checksums", str(root / "checksums.sha256"),
            ]
            with mock.patch("sys.argv", argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main()

    def test_current_ipresolve_is_separate_from_exact_ip_and_subnet(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            start = int(ipaddress.ip_address("203.0.114.1"))
            resolver_rows = [str(ipaddress.ip_address(start + i)) for i in range(1005)]
            (root / "ipresolve.lst").write_text("\n".join(resolver_rows) + "\n", encoding="utf-8")
            base_start = int(ipaddress.ip_address("192.0.20.1"))
            baseline_rows = [str(ipaddress.ip_address(base_start + i)) for i in range(1005)]
            (root / "baseline.txt").write_text("\n".join(baseline_rows) + "\n", encoding="utf-8")
            exact_rows = [str(ipaddress.ip_address(int(ipaddress.ip_address("198.51.20.1")) + i)) for i in range(1005)]
            (root / "ip.lst").write_text("\n".join(exact_rows) + "\n", encoding="utf-8")
            (root / "subnet.lst").write_text("198.51.30.0/24\n", encoding="utf-8")
            for name in ("community.lst", "ipsum.lst"):
                (root / name).write_text("", encoding="utf-8")
            argv = [
                "prepare_blocked_sources_v41.py",
                "--ip-list", str(root / "ip.lst"),
                "--ipresolve", str(root / "ipresolve.lst"),
                "--baseline", str(root / "baseline.txt"),
                "--subnet", str(root / "subnet.lst"),
                "--community", str(root / "community.lst"),
                "--refilter", str(root / "ipsum.lst"),
                "--approved", str(root / "approved.txt"),
                "--exact-approved", str(root / "exact.txt"),
                "--resolved-approved", str(root / "resolved.txt"),
                "--review", str(root / "review.tsv"),
                "--stats", str(root / "stats.tsv"),
                "--checksums", str(root / "checksums.sha256"),
            ]
            with mock.patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            exact = (root / "exact.txt").read_text(encoding="utf-8")
            resolved = (root / "resolved.txt").read_text(encoding="utf-8")
            self.assertIn("198.51.20.1/32", exact)
            self.assertIn("198.51.30.0/24", exact)
            self.assertIn("192.0.20.1/32", exact)  # legacy baseline is unclassified and stays hard
            self.assertIn("203.0.114.1/32", resolved)
            self.assertNotIn("203.0.114.1/32", exact)



    def test_pinned_v38_raw_feeds_restore_only_proven_resolver_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def host_rows(start):
                first = int(ipaddress.ip_address(start))
                return "\n".join(str(ipaddress.ip_address(first + i)) for i in range(1005)) + "\n"
            (root / "baseline.txt").write_text(host_rows("192.0.20.1"), encoding="utf-8")
            (root / "hist-resolve.txt").write_text(host_rows("192.0.20.1"), encoding="utf-8")
            (root / "hist-ip.txt").write_text(host_rows("198.51.20.1"), encoding="utf-8")
            (root / "hist-subnet.txt").write_text("192.0.20.0/24\n", encoding="utf-8")
            (root / "ip.lst").write_text(host_rows("198.51.20.1"), encoding="utf-8")
            (root / "ipresolve.lst").write_text("", encoding="utf-8")
            (root / "subnet.lst").write_text("198.51.30.0/24\n", encoding="utf-8")
            for name in ("community.lst", "ipsum.lst"):
                (root / name).write_text("", encoding="utf-8")
            argv = [
                "prepare_blocked_sources_v41.py",
                "--ip-list", str(root / "ip.lst"),
                "--ipresolve", str(root / "ipresolve.lst"),
                "--baseline", str(root / "baseline.txt"),
                "--historical-ip-list", str(root / "hist-ip.txt"),
                "--historical-ipresolve", str(root / "hist-resolve.txt"),
                "--historical-subnet", str(root / "hist-subnet.txt"),
                "--subnet", str(root / "subnet.lst"),
                "--community", str(root / "community.lst"),
                "--refilter", str(root / "ipsum.lst"),
                "--approved", str(root / "approved.txt"),
                "--exact-approved", str(root / "exact.txt"),
                "--resolved-approved", str(root / "resolved.txt"),
                "--review", str(root / "review.tsv"),
                "--stats", str(root / "stats.tsv"),
                "--checksums", str(root / "checksums.sha256"),
            ]
            with mock.patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            exact = (root / "exact.txt").read_text(encoding="utf-8")
            resolver = (root / "resolved.txt").read_text(encoding="utf-8")
            self.assertIn("192.0.20.1/32", exact)
            self.assertNotIn("192.0.20.1/32", resolver)
            self.assertIn("192.0.21.1/32", resolver)
            self.assertNotIn("192.0.21.1/32", exact)
            self.assertIn("198.51.20.1/32", exact)
            self.assertIn("v38-historical-ipresolve-only", resolver)
            self.assertIn("v38-historical-ipresolve.lst", (root / "stats.tsv").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
