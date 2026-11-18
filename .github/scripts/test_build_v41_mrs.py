import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import build_v41_mrs as mrs
from build_v41_overlay import encode_geoip
from v41_release_manifest import PRIVATE_MRS, RU_MRS


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
                mrs.compile_and_verify(wrong, root, [], [])
            convert.assert_not_called()

    def test_forbidden_private_artifact_is_rejected_before_conversion(self):
        for name in PRIVATE_MRS:
            with self.subTest(name=name), TemporaryDirectory() as directory, patch.object(mrs, "convert") as convert:
                root = Path(directory)
                (root / name).symlink_to("missing")
                with self.assertRaisesRegex(ValueError, "Forbidden v41 artifact"):
                    mrs.compile_and_verify(root / "mihomo", root, [], [])
                convert.assert_not_called()


@unittest.skipUnless(os.environ.get("V41_TEST_MIHOMO"), "set V41_TEST_MIHOMO to the pinned binary")
class OfficialMrsTests(unittest.TestCase):
    def setUp(self):
        self.mihomo = Path(os.environ["V41_TEST_MIHOMO"])
        self.assertEqual(mrs.digest(self.mihomo), mrs.MIHOMO_SHA256)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output = Path(temp.name)
        self.ru = nets("198.51.100.0/25", "198.51.100.128/25", "2001:db8::/32")

    def test_builds_and_reverifies_only_ru(self):
        mrs.compile_and_verify(self.mihomo, self.output, self.ru, self.ru)
        self.assertEqual({p.name for p in self.output.iterdir()}, {RU_MRS, f"{RU_MRS}.sha256sum"})
        binary = self.output / RU_MRS
        sidecar = self.output / f"{RU_MRS}.sha256sum"
        self.assertTrue(binary.read_bytes().startswith(mrs.ZSTD_MAGIC))
        self.assertEqual(sidecar.read_text(), f"{mrs.digest(binary)}  {RU_MRS}\n")
        mrs.compile_and_verify(self.mihomo, self.output, self.ru, self.ru, verify_only=True)
        sidecar.write_text("wrong\n")
        with self.assertRaisesRegex(ValueError, "checksum sidecar does not match"):
            mrs.compile_and_verify(self.mihomo, self.output, self.ru, self.ru, verify_only=True)

    def test_private_ipv4_mapped_regression_is_still_detected_in_fixture(self):
        expected = nets("::ffff:0:0/96")
        source = self.output / "mapped.txt"
        source.write_text("::ffff:0:0/96\n")
        binary = self.output / "mapped-regression-fixture.mrs"
        mrs.convert(self.mihomo, "text", source, binary)
        decompiled = self.output / "mapped.roundtrip.txt"
        with self.assertRaisesRegex(ValueError, r"IPv4 \+4294967296 / -0.*IPv6 \+0 / -4294967296"):
            mrs.verify_mrs(self.mihomo, binary, decompiled, expected)
        self.assertEqual(decompiled.read_text(), "0.0.0.0/0\n")
        self.assertTrue(all(not (self.output / name).exists() for name in PRIVATE_MRS))

    def test_ru_disagreement_with_srs_fails_without_outputs(self):
        wrong = nets("198.51.101.0/24", "2001:db8::/32")
        with self.assertRaisesRegex(ValueError, r"geoip_RU\.srs.*IPv4 \+256 / -256"):
            mrs.compile_and_verify(self.mihomo, self.output, self.ru, wrong)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_ru_disagreement_with_dat_fails_despite_valid_sidecar(self):
        mrs.compile_and_verify(self.mihomo, self.output, self.ru, self.ru)
        with self.assertRaisesRegex(ValueError, r"Full DAT.*IPv6"):
            mrs.compile_and_verify(self.mihomo, self.output, self.ru[:-1], self.ru, verify_only=True)

    @unittest.skipUnless(os.environ.get("V41_TEST_SING_BOX"), "set V41_TEST_SING_BOX to the pinned binary")
    def test_cli_preserves_dat_and_both_srs_even_with_mapped_private(self):
        sing_box = os.environ["V41_TEST_SING_BOX"]
        dat = self.output / "geoip_RU.dat"
        dat.write_bytes(encode_geoip({"RU": self.ru, "PRIVATE": nets("::ffff:0:0/96", "10.0.0.0/8")}))
        manifest = self.output / "manifest.json"
        manifest.write_text(json.dumps({"output_sha256": mrs.digest(dat)}))
        scripts = Path(mrs.__file__).parent
        metrics = self.output / "metrics.json"
        subprocess.run([sys.executable, scripts / "build_v41_srs.py", "--full", dat, "--manifest", manifest,
                        "--sing-box", sing_box, "--metrics", metrics], check=True, capture_output=True)
        ru_srs = self.output / "geoip_RU.srs"
        inputs = (dat, ru_srs, self.output / "geoip_PRIVATE.srs")
        before = {path: path.read_bytes() for path in inputs}
        command = [sys.executable, scripts / "build_v41_mrs.py", "--full", dat, "--manifest", manifest,
                   "--sing-box", sing_box, "--ru-srs", ru_srs, "--mihomo", self.mihomo, "--output", self.output]
        subprocess.run([*command, "--metrics", metrics], check=True, capture_output=True)
        subprocess.run([*command, "--verify-only"], check=True, capture_output=True)
        self.assertEqual({path: path.read_bytes() for path in inputs}, before)
        categories = json.loads(metrics.read_bytes())["categories"]
        self.assertEqual(categories["RU"]["mrs_bytes"], (self.output / RU_MRS).stat().st_size)
        self.assertNotIn("mrs_bytes", categories["PRIVATE"])
        self.assertTrue(all(not (self.output / name).exists() for name in PRIVATE_MRS))

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
