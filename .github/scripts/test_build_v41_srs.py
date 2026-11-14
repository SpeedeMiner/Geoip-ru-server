import hashlib
import ipaddress
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_v41_overlay import encode_geoip
from build_v41_srs import check_dat


class FullSrsValidationTests(unittest.TestCase):
    def check(self, categories, *, bad_digest=False):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            dat, manifest = root / "geoip_RU.dat", root / "manifest.json"
            payload = encode_geoip({
                name: {ipaddress.ip_network(x) for x in values}
                for name, values in categories.items()
            })
            dat.write_bytes(payload)
            digest = "0" * 64 if bad_digest else hashlib.sha256(payload).hexdigest()
            manifest.write_text(json.dumps({"output_sha256": digest}))
            return check_dat(dat, manifest)

    def test_valid_dat_decodes_both_categories(self):
        categories = {"RU": {"192.0.2.1/32", "2001:db8::/48"}, "PRIVATE": {"10.0.0.0/8", "fc00::/7"}}
        self.assertEqual({k: {str(n) for n in v} for k, v in self.check(categories).items()}, categories)

    def test_rejects_wrong_digest(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.check({"RU": {"192.0.2.1/32"}, "PRIVATE": {"10.0.0.0/8"}}, bad_digest=True)

    def test_rejects_overlap_in_either_family(self):
        for shared in ("192.0.2.1/32", "2001:db8::/48"):
            with self.subTest(shared=shared), self.assertRaisesRegex(ValueError, "overlap"):
                self.check({"RU": {shared}, "PRIVATE": {shared}})

    def test_rejects_unexpected_category(self):
        with self.assertRaisesRegex(ValueError, "categories only"):
            self.check({"RU": {"192.0.2.1/32"}, "PRIVATE": {"10.0.0.0/8"}, "OTHER": {"203.0.113.1/32"}})


if __name__ == "__main__":
    unittest.main()
