import hashlib
import ipaddress
import json
from pathlib import Path
import tempfile
import unittest

from build_v41_light_srs import check_dat
from build_v41_overlay import encode_geoip


def nets(*values):
    return {ipaddress.ip_network(x) for x in values}


class LightSrsValidationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.full, self.light, self.manifest = (root / f for f in ("full.dat", "light.dat", "manifest.json"))
        self.ru = nets("192.0.2.0/31", "2001:db8::/48")
        self.private = nets("10.0.0.0/8", "fc00::/7")
        self.full.write_bytes(encode_geoip({"RU": self.ru | nets("198.51.100.3/32"), "PRIVATE": self.private}))

    def fixture(self, ru, private, removed=1):
        self.light.write_bytes(encode_geoip({"RU": ru, "PRIVATE": private}))
        self.manifest.write_text(json.dumps({
            "output_sha256": hashlib.sha256(self.full.read_bytes()).hexdigest(),
            "light_output": {
                "sha256": hashlib.sha256(self.light.read_bytes()).hexdigest(),
                "removed_address_space": {"ipv4": removed, "ipv6": 0},
            },
        }))

    def test_valid_light_decodes_to_exact_categories(self):
        self.fixture(self.ru, self.private)
        self.assertEqual(check_dat(self.full, self.light, self.manifest), {"RU": self.ru, "PRIVATE": self.private})

    def test_hash_mismatch_fails_before_using_dat(self):
        self.fixture(self.ru, self.private)
        self.light.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            check_dat(self.full, self.light, self.manifest)

    def test_extra_direct_address_is_never_allowed(self):
        self.fixture(self.ru | nets("203.0.113.4/32"), self.private)
        with self.assertRaisesRegex(ValueError, "coverage"):
            check_dat(self.full, self.light, self.manifest)

    def test_private_and_measured_delta_must_match(self):
        self.fixture(self.ru, nets("10.0.0.0/8"))
        with self.assertRaisesRegex(ValueError, "PRIVATE"):
            check_dat(self.full, self.light, self.manifest)
        self.fixture(self.ru, self.private, removed=0)
        with self.assertRaisesRegex(ValueError, "coverage"):
            check_dat(self.full, self.light, self.manifest)
