import hashlib
import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import build_v41_overlay as builder
import validate_v41_publication_bounds as gate


class PublicationBoundsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old = self.make("old.dat", ["198.18.0.0/19", "2001:db8:1::/48"])

    def make(self, name, rows):
        p = self.root / name
        p.write_bytes(builder.encode_geoip({
            "RU": {ipaddress.ip_network(x) for x in rows},
            "PRIVATE": {ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("fc00::/7")},
        }))
        return p

    def test_publication_absolute_limit_not_bypassable(self):
        p = self.make("bad.dat", ["0.0.0.0/1", "2001:db8:1::/48"])
        with self.assertRaisesRegex(ValueError, "wider"):
            gate.validate(p, self.old, hashlib.sha256(p.read_bytes()).hexdigest())

    def test_equal_size_substitution_requires_exact_review_digest(self):
        p = self.make("swap.dat", ["198.19.0.0/19", "2001:db8:1::/48"])
        with self.assertRaisesRegex(ValueError, "delta exceeds"):
            gate.validate(p, self.old)
        gate.validate(p, self.old, hashlib.sha256(p.read_bytes()).hexdigest())

    def test_small_address_delta(self):
        p = self.make("ok.dat", ["198.18.0.0/19", "2001:db8:1::/48", "198.18.40.1/32"])
        gate.validate(p, self.old)

    def test_strict_and_inverted_fields(self):
        with self.assertRaises(ValueError):
            builder.parse_network("1.2.3.4/8")
        with self.assertRaises(ValueError):
            builder.parse_network("8.8.8.8", False)
        self.assertEqual(str(builder.parse_network("8.8.8.8/32", False)), "8.8.8.8/32")
        bad_cidr = builder.field_bytes(1, bytes([1, 2, 3, 4])) + builder.field_varint(2, 8)
        p = self.root / "bad.dat"
        p.write_bytes(builder.field_bytes(1, builder.field_bytes(1,b"RU") + builder.field_bytes(2,bad_cidr)))
        for reader in (builder.parse_geoip_dat, gate.read):
            with self.assertRaises(ValueError):
                reader(p)
        p.write_bytes(builder.field_bytes(1, builder.field_bytes(1,b"RU") + builder.field_varint(3,1)))
        for reader in (builder.parse_geoip_dat, gate.read):
            with self.assertRaises(ValueError):
                reader(p)
