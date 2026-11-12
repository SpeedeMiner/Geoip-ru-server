import ipaddress
import tempfile
import unittest
from pathlib import Path

from build_v41_overlay import (
    encode_geoip, hydra_expected_after_policy, intervals, parse_hydra_direct_whitelist,
    subtract,
)


def net(*values):
    return {ipaddress.ip_network(v) for v in values}


class HydraDirectWhitelistCoverageTests(unittest.TestCase):
    def make_hydra(self, categories):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "hydra.dat"
        path.write_bytes(encode_geoip(categories))
        return path

    def test_both_categories_accepted_with_exact_provenance(self):
        path = self.make_hydra({
            "DIRECT": net("198.51.100.0/24", "2001:db8:1::/48"),
            "WHITELIST": net("203.0.113.0/24"),
            "PRIVATE": net("10.0.0.0/8"),
        })
        result = parse_hydra_direct_whitelist(path)
        self.assertEqual(set(result), {"hydra-direct", "hydra-whitelist"})
        self.assertEqual(result["hydra-direct"], net("198.51.100.0/24", "2001:db8:1::/48"))
        self.assertEqual(result["hydra-whitelist"], net("203.0.113.0/24"))

    def test_private_and_exact_blocks_win_without_discarding_unblocked_subnets(self):
        path = self.make_hydra({
            "DIRECT": net("198.51.100.0/24"),
            "WHITELIST": net("203.0.113.0/24"),
        })
        hydra = parse_hydra_direct_whitelist(path)
        final = hydra_expected_after_policy(
            hydra,
            net("198.51.100.0/25"),
            net("203.0.113.128/25"),
        )
        self.assertEqual(
            intervals(final, 4),
            intervals(net("198.51.100.128/25", "203.0.113.0/25"), 4),
        )

    def test_missing_whitelist_fails_closed(self):
        path = self.make_hydra({"DIRECT": net("198.51.100.0/24")})
        with self.assertRaisesRegex(ValueError, "missing"):
            parse_hydra_direct_whitelist(path)

    def test_default_route_fails_closed(self):
        path = self.make_hydra({
            "DIRECT": net("0.0.0.0/0"),
            "WHITELIST": net("203.0.113.0/24"),
        })
        with self.assertRaisesRegex(ValueError, "default route"):
            parse_hydra_direct_whitelist(path)


if __name__ == "__main__":
    unittest.main()
