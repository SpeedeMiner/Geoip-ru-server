from __future__ import annotations

import argparse
import csv
import ipaddress
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_v37_canonical_prefix_inventory import (  # noqa: E402
    InventoryError,
    build_inventory,
    parse_geoip_list,
    parse_cidr_message,
)


def varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def field_bytes(number: int, value: bytes) -> bytes:
    return varint((number << 3) | 2) + varint(len(value)) + value


def field_varint(number: int, value: int) -> bytes:
    return varint(number << 3) + varint(value)


def geoip_entry(code: str, prefixes: list[str]) -> bytes:
    entry = field_bytes(1, code.encode())
    for value in prefixes:
        network = ipaddress.ip_network(value, strict=True)
        cidr = field_bytes(1, network.network_address.packed) + field_varint(2, network.prefixlen)
        entry += field_bytes(2, cidr)
    return entry


def geoip_list(entries: list[tuple[str, list[str]]]) -> bytes:
    return b"".join(field_bytes(1, geoip_entry(code, prefixes)) for code, prefixes in entries)


class V37CanonicalInventoryTests(unittest.TestCase):
    def test_protobuf_geoip_list_extracts_exact_ru_and_private_prefixes(self):
        raw = geoip_list([
            ("RU", ["8.8.8.0/24", "2001:db8::/32"]),
            ("PRIVATE", ["10.0.0.0/8"]),
            ("US", ["1.1.1.0/24"]),
        ])
        parsed = parse_geoip_list(raw)
        self.assertEqual(parsed["ru"], {"8.8.8.0/24", "2001:db8::/32"})
        self.assertEqual(parsed["private"], {"10.0.0.0/8"})

    def test_cidr_message_rejects_invalid_prefix_length(self):
        raw = field_bytes(1, ipaddress.ip_address("192.0.2.0").packed) + field_varint(2, 33)
        with self.assertRaisesRegex(InventoryError, "out of range"):
            parse_cidr_message(raw)

    def test_inventory_keeps_parent_and_child_as_distinct_exact_nlri(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "geoip.dat").write_bytes(geoip_list([
                ("RU", ["8.8.0.0/16"]),
                ("PRIVATE", ["10.0.0.0/8"]),
            ]))
            (root / "selected.txt").write_text(
                "8.8.8.0/24 # AS12345[RIR-RU]\n1.1.1.0/24 # AS64500\n",
                encoding="utf-8",
            )
            (root / "rir.txt").write_text("8.8.8.0/24\n9.9.9.0/24\n", encoding="utf-8")
            (root / "global.txt").write_text("8.8.8.0/24\n4.4.4.0/24\n", encoding="utf-8")
            (root / "additional.tsv").write_text(
                "PREFIX\tFAMILY\tPREFIX_ADDRESSES\tGROUPS_WITH_OVERLAP\n"
                "8.8.8.0/24\tIPv4\t256\tdavoyan\n",
                encoding="utf-8",
            )
            (root / "blocked.txt").write_text("8.8.8.0/24 # source=test\n", encoding="utf-8")
            (root / "review.tsv").write_text(
                "SOURCE\tPREFIX\tREASON\nreview\t6.6.6.0/24\tmanual\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                geoip_dat=root / "geoip.dat",
                selected_bgp=root / "selected.txt",
                rir_ru=root / "rir.txt",
                global_bgp=root / "global.txt",
                additional_provenance=root / "additional.tsv",
                blocked_approved=root / "blocked.txt",
                blocked_review=root / "review.tsv",
                output=root / "inventory.tsv",
                stats=root / "stats.txt",
                release_commit="d613c5f0ef482f2051cbc37a303b2ac30076d313",
                geoip_sha256="a" * 64,
            )
            result = build_inventory(args)
            with args.output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            by_prefix = {row["PREFIX"]: row for row in rows}
            self.assertIn("8.8.0.0/16", by_prefix)
            self.assertIn("8.8.8.0/24", by_prefix)
            self.assertEqual(len(rows), 7)
            self.assertEqual(by_prefix["8.8.0.0/16"]["IN_V37_RU_OUTPUT"], "yes")
            self.assertEqual(by_prefix["8.8.0.0/16"]["IN_SELECTED_RIR_OR_COMPANY_ORIGIN_BGP"], "no")
            self.assertEqual(by_prefix["8.8.8.0/24"]["IN_V37_RU_OUTPUT"], "no")
            self.assertEqual(by_prefix["8.8.8.0/24"]["SELECTED_ORIGIN_ASNS"], "AS12345")
            self.assertEqual(by_prefix["8.8.8.0/24"]["IN_RIR_RU_REGISTERED_RESOURCES"], "yes")
            self.assertEqual(by_prefix["8.8.8.0/24"]["IN_ACCEPTED_ADDITIONAL_GEOIP_FEEDS"], "yes")
            self.assertEqual(by_prefix["8.8.8.0/24"]["IN_APPROVED_BLOCKED_EXCLUSIONS"], "yes")
            self.assertEqual(by_prefix["6.6.6.0/24"]["IN_BLOCKED_REVIEW_ONLY_CANDIDATES"], "yes")
            self.assertEqual(result["output_ru"], 1)
            self.assertEqual(result["selected_bgp"], 2)
            stats = args.stats.read_text(encoding="utf-8")
            self.assertIn("Parent/child CIDRs are not inferred as exact matches", stats)

    def test_empty_or_invalid_geoip_file_fails_closed(self):
        with self.assertRaisesRegex(InventoryError, "empty"):
            parse_geoip_list(b"")
        with self.assertRaises(InventoryError):
            parse_geoip_list(b"\x0a\x05\x0a\x01R")


if __name__ == "__main__":
    unittest.main()
