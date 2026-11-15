import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_v41_iana_special_prefixes import read_registry


class IanaParsingTests(unittest.TestCase):
    def parse(self, rows, family=4):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "iana.csv"
            p.write_text("Address Block,Globally Reachable\n" + rows, encoding="utf-8")
            return read_registry(p, family)

    def test_footnotes_and_multiple_cidrs(self):
        private, public = self.parse(
            '192.0.0.0/24 [2],False [1]\n'
            '"192.0.0.170/32, 192.0.0.171/32 [3]",False\n'
            '192.0.0.9/32,True\n'
            '192.88.99.0/24,\n'
        )
        self.assertEqual({str(n) for n in private},
                         {"192.0.0.0/24", "192.0.0.170/32", "192.0.0.171/32"})
        self.assertEqual(public, {ipaddress.ip_network("192.0.0.9/32")})

    def test_ipv6_na_is_not_a_block_or_an_exception(self):
        private, public = self.parse(
            '2001::/32,N/A [2]\n2002::/16 [3],N/A [3]\n'
            'fc00::/7,False\n2001:3::/32,True\n', 6)
        self.assertEqual({str(n) for n in private}, {"fc00::/7"})
        self.assertEqual({str(n) for n in public}, {"2001:3::/32"})

    def test_known_status_requires_valid_canonical_same_family_cidr(self):
        for token in ("bad", "192.0.2.1", "192.0.2.1/24", "0.0.0.0/0", "2001:db8::/32"):
            with self.subTest(token=token), self.assertRaisesRegex(ValueError, "invalid IPv4 CIDR"):
                self.parse(f"{token},False\n192.0.0.9/32,True\n")

    def test_exact_prefix_conflict_rejected(self):
        with self.assertRaisesRegex(ValueError, "conflicting reachability"):
            self.parse("192.0.0.9/32,False\n192.0.0.9/32,True\n")


if __name__ == "__main__":
    unittest.main()
