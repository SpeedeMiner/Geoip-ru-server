import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_v41_iana_special_prefixes import MINIMUM_PREFIXES, read_registry, read_required_registry


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

    def test_unknown_status_still_requires_well_formed_cidr(self):
        with self.assertRaisesRegex(ValueError, "invalid IPv6 CIDR"):
            self.parse("garbage,N/A\nfc00::/7,False\n2001:3::/32,True\n", 6)

    def test_independent_floors_reject_each_partial_registry(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "iana.csv"
            for family, (min_private, min_public) in MINIMUM_PREFIXES.items():
                a, b = (("192.0.2.0", "198.51.100.0") if family == 4 else ("2001:db8::", "2001:db8:1::"))
                ip, suffix = ((ipaddress.IPv4Address, 32) if family == 4 else (ipaddress.IPv6Address, 128))
                private = [f"{ip(int(ip(a)) + i)}/{suffix},False\n" for i in range(min_private)]
                public = [f"{ip(int(ip(b)) + i)}/{suffix},True\n" for i in range(min_public)]
                for rows in (private[:-1] + public + private[:1], private + public[:-1] + public[:1]):
                    with self.subTest(family=family, rows=rows):
                        p.write_text("Address Block,Globally Reachable\n" + "".join(rows))
                        with self.assertRaisesRegex(ValueError, f"unusually small IPv{family}"):
                            read_required_registry(p, family)
                p.write_text("Address Block,Globally Reachable\n" + "".join(private + public))
                self.assertEqual(tuple(map(len, read_required_registry(p, family))), (min_private, min_public))

    def test_exact_prefix_conflict_rejected(self):
        with self.assertRaisesRegex(ValueError, "conflicting reachability"):
            self.parse("192.0.0.9/32,False\n192.0.0.9/32,True\n")


if __name__ == "__main__":
    unittest.main()
