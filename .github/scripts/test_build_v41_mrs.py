import ipaddress
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import build_v41_mrs as mrs


def nets(*cidrs):
    return [ipaddress.ip_network(cidr) for cidr in cidrs]


class MrsTests(unittest.TestCase):
    def test_compare_unions_not_prefix_counts_or_order(self):
        mrs.verify_coverage("2001:db8::/32\n198.51.100.0/24\n", nets(
            "198.51.100.0/25", "198.51.100.128/25", "2001:db8::/32",
        ), "fixture.mrs")

    def test_compare_separates_families_even_for_mapped_ipv6(self):
        with self.assertRaisesRegex(ValueError, r"IPv4 \+4294967296 / -0.*IPv6 \+0 / -4294967296"):
            mrs.verify_coverage("0.0.0.0/0\n", nets("::ffff:0:0/96"), "fixture.mrs")

    def test_same_count_for_different_prefixes_does_not_pass(self):
        with self.assertRaisesRegex(ValueError, r"IPv4 \+256 / -256"):
            mrs.verify_coverage("198.51.101.0/24\n", nets("198.51.100.0/24"), "fixture.mrs")

    def test_rejects_invalid_cidr_export(self):
        for text in ("", "127.0.0.1\n", "10.0.0.1/8\n", "payload:\n  - 10.0.0.0/8\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                mrs.verify_coverage(text, nets("10.0.0.0/8"), "fixture.mrs")

    def test_non_zstd_payload_rejected_before_decoder(self):
        with TemporaryDirectory() as directory, patch.object(mrs, "convert") as convert:
            root = Path(directory)
            binary = root / "wrong.mrs"
            binary.write_text("10.0.0.0/8\n")
            with self.assertRaisesRegex(ValueError, "Unexpected MRS frame"):
                mrs.verify_mrs("unused", binary, root / "wrong.txt", nets("10.0.0.0/8"))
            convert.assert_not_called()

    def test_rejects_unpinned_binary_before_execution(self):
        with TemporaryDirectory() as directory, patch.object(mrs, "convert") as convert:
            root = Path(directory)
            wrong = root / "mihomo"
            wrong.write_bytes(b"not the official binary")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                mrs.compile_and_verify(wrong, root, {})
            convert.assert_not_called()


@unittest.skipUnless(os.environ.get("V41_TEST_MIHOMO"), "set V41_TEST_MIHOMO to the pinned binary")
class OfficialMrsTests(unittest.TestCase):
    def setUp(self):
        self.mihomo = Path(os.environ["V41_TEST_MIHOMO"])
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output = Path(temp.name)
        self.categories = {"RU": nets("198.51.100.0/25", "198.51.100.128/25", "2001:db8::/32"),
                           "PRIVATE": nets("10.0.0.0/8", "fc00::/7")}

    def test_builds_both_official_ipcidr_rule_sets_and_sidecars(self):
        mrs.compile_and_verify(self.mihomo, self.output, self.categories)
        self.assertEqual(len(list(self.output.iterdir())), 4)
        for name in mrs.MRS_NAMES.values():
            binary = self.output / name
            self.assertTrue(binary.read_bytes().startswith(mrs.ZSTD_MAGIC))
            self.assertEqual((self.output / f"{name}.sha256sum").read_text(),
                             f"{mrs.digest(binary)}  {name}\n")

    def test_private_ipv4_mapped_regression_leaves_no_partial_outputs(self):
        self.categories["PRIVATE"] += nets("::ffff:0:0/96")
        with self.assertRaisesRegex(ValueError, r"geoip_PRIVATE\.mrs .*IPv4.*IPv6"):
            mrs.compile_and_verify(self.mihomo, self.output, self.categories)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_official_decoder_rejects_wrong_behavior(self):
        source = self.output / "domain.txt"
        source.write_text("example.org\n")
        binary = self.output / "domain.mrs"
        subprocess.run([self.mihomo, "convert-ruleset", "domain", "text", source, binary], check=True)
        result = subprocess.run([self.mihomo, "convert-ruleset", "ipcidr", "mrs", binary,
                                 self.output / "ipcidr.txt"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid behavior", result.stderr)


if __name__ == "__main__":
    unittest.main()
