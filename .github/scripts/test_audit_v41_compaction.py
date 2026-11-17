import ipaddress
from pathlib import Path
import tempfile
import unittest

import audit_v41_compaction as audit
from build_v41_overlay import intervals


def nets(*values):
    return {ipaddress.ip_network(value) for value in values}


class CompactionAuditTests(unittest.TestCase):
    def test_threshold_uses_collapsed_fragments_and_exact_address_sum(self):
        block = ipaddress.IPv4Network("11.0.0.0/23")
        parts = set(block.address_exclude(ipaddress.IPv4Network("11.0.0.1/32")))
        self.assertEqual(len(audit.fragment_blocks(parts)[block]), 9)
        self.assertNotIn(block, audit.fragment_blocks(parts | nets("11.0.0.1/32")))
        self.assertNotIn(block, audit.fragment_blocks(
            parts - nets("11.0.1.0/24", "11.0.0.128/25")))

    def test_single_origin_uses_most_specific_route_and_refuses_moas(self):
        block = ipaddress.IPv4Network("11.0.0.0/23")
        left = ipaddress.IPv4Network("11.0.0.0/24")
        right = ipaddress.IPv4Network("11.0.1.0/24")
        parent = ipaddress.IPv4Network("11.0.0.0/20")
        direct = [audit.bounds(left)]
        self.assertEqual(audit.single_origin(block, direct, [(2, parent), (1, block)]), (1, []))
        self.assertEqual(audit.single_origin(block, direct, [(2, block), (1, block)]), (None, []))
        self.assertEqual(audit.single_origin(block, direct, [(1, block), (2, right)]), (None, []))
        self.assertEqual(audit.single_origin(block, direct, [(1, left)]), (1, [audit.bounds(right)]))
        self.assertEqual(audit.single_origin(block, direct, [(1, right)]), (None, []))

    def test_gap_layers_record_exact_addresses_even_if_they_overlap(self):
        block = ipaddress.IPv4Network("11.0.0.0/23")
        direct = intervals(nets("11.0.0.0/24"), 4)
        masks = {"hard": intervals(nets("11.0.1.0/25", "11.0.0.0/24"), 4),
                 "soft": intervals(nets("11.0.1.0/24"), 4)}
        gaps = audit.classify_gaps(block, direct, masks)
        self.assertEqual(audit.as_text(gaps["hard"]), ["11.0.1.0/25"])
        self.assertEqual(audit.as_text(gaps["soft"]), ["11.0.1.0/24"])

    def test_resolver_witness_rejects_partial_and_other_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blocked.tsv"
            path.write_text(
                "source_id\tfamily\tprefix\taddresses\toverlap_preblock_direct\n"
                "v41-resolver-only-candidates\tIPv4\t11.0.0.1/32\t1\t1\n"
                "v41-resolver-only-candidates\tIPv4\t11.0.1.0/24\t256\t255\n"
                "v41-exact-and-legacy-hard-blocks\tIPv4\t11.0.0.2/32\t1\t1\n",
                encoding="utf-8",
            )
            self.assertEqual(audit.as_text(audit.resolver_witness(path)), ["11.0.0.1/32"])

    def test_published_metrics_use_whole_union_and_keep_ipv6_and_private(self):
        categories = {"RU": nets("11.0.0.0/24", "11.0.1.128/25", "2001:db8::/48"),
                      "PRIVATE": nets("10.0.0.0/8")}
        before = intervals(categories["RU"], 4)
        addition = intervals(nets("11.0.1.0/25", "11.0.0.1/32"), 4)
        old = audit.stats(before, [], categories)
        new = audit.stats(before, addition, categories)
        self.assertEqual((old["ipv4_cidrs"], new["ipv4_cidrs"], new["added_ipv4"]), (2, 1, 128))
        self.assertEqual(old["dat_bytes"] - new["dat_bytes"], 10)
