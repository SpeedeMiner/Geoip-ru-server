import hashlib
import ipaddress
import tempfile
import unittest
from datetime import date
from pathlib import Path

from v41_direct_admission import CDN_KEY, HEADER, cdn_networks, read_cdn, verify_cdn_manifest


class CDNAdmissionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "cdn.tsv"
        self.row = ("8.8.8.8\tExample CDN\thttps://example.test/prefix\tAS321\t"
                    "https://example.test/measure\t2020-01-01\t2099-01-01")
        self.as_of = date(2026, 11, 16)

    def write(self, *rows):
        self.path.write_text("\n".join(["\t".join(HEADER), *rows]) + "\n", encoding="utf-8")

    def test_empty_registry_adds_nothing_and_is_bound(self):
        self.write()
        self.assertEqual(read_cdn(self.path), {})
        manifest = {"input_sha256": {CDN_KEY: hashlib.sha256(self.path.read_bytes()).hexdigest()},
                    CDN_KEY: {"records": []}}
        self.assertEqual(verify_cdn_manifest(manifest, self.path), {})
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            verify_cdn_manifest({}, self.path)

    def test_dual_stack_rows_never_promote_neighboring_addresses(self):
        self.write(self.row, self.row.replace("8.8.8.8", "2606:4700::2"))
        result = cdn_networks(read_cdn(self.path, as_of=self.as_of))
        self.assertEqual(result, {ipaddress.ip_network(s) for s in ("8.8.8.8/32", "2606:4700::2/128")})

    def test_rejects_ranges_unqualified_evidence_bad_asn_and_expiry(self):
        for broken in (
            self.row.replace("8.8.8.8", "8.8.8.0/24"),
            self.row.replace("8.8.8.8", "10.0.0.1"),
            self.row.replace("8.8.8.8", "::ffff:808:808"),
            self.row.replace("8.8.8.8", "ff02::1"),
            self.row.replace("AS321", "AS0"),
            self.row.replace("https://example.test/measure", "https://example.test/prefix"),
            self.row.replace("https://example.test/measure", "https://example.test/"),
            self.row.replace("https://example.test/measure", "http://example.test/measure"),
            self.row.replace("2099-01-01", "2021-01-01"),
        ):
            with self.subTest(row=broken):
                self.write(broken)
                with self.assertRaises(ValueError):
                    read_cdn(self.path, as_of=self.as_of)
        self.write(self.row, self.row)
        with self.assertRaises(ValueError):
            read_cdn(self.path, as_of=self.as_of)
