from datetime import date
import hashlib
import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from build_v41_overlay import reviewed_unreachable_mask
from v41_reviewed_unreachable import read_reviewed
import validate_v41_overlay as validation


def nets(*rows):
    return {ipaddress.ip_network(row) for row in rows}


class ReviewedUnreachableTests(unittest.TestCase):
    def test_evidence_must_be_current_and_ip_specific(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "records.tsv"
            header = "cidr\tkind\tevidence\tverified_on\treview_after\n"
            path.write_text(header, encoding="utf-8")
            self.assertEqual(read_reviewed(path, as_of=date(2026, 11, 16)), {})
            row = "192.0.2.0/24\tIP_LAYER_BLOCK\thttps://example.test/evidence\t2026-11-15\t2026-12-01\n"
            path.write_text(header + row, encoding="utf-8")
            self.assertEqual(len(read_reviewed(path, as_of=date(2026, 11, 16))), 1)
            for bad in (row.replace("IP_LAYER_BLOCK", "SNI_BLOCK"),
                        row.replace("https://example.test/evidence", "https://example.test"),
                        row.replace("2026-12-01", "2026-11-15")):
                path.write_text(header + bad, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_reviewed(path, as_of=date(2026, 11, 16))

    def test_unreachable_subtraction_preserves_protected_core_in_both_families(self):
        records = {"192.0.2.0/24": {}, "2001:db8::/120": {}}
        protected = nets("192.0.2.0/25", "2001:db8::/121")
        self.assertEqual(reviewed_unreachable_mask(records, protected),
                         nets("192.0.2.128/25", "2001:db8::80/121"))
        self.assertFalse(reviewed_unreachable_mask(records, nets(*records)))

    def test_manifest_binds_input_and_core_mask(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "records.tsv"
            path.write_text("evidence", encoding="utf-8")
            records = {"192.0.2.0/24": {"cidr": "192.0.2.0/24"}}
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest = {"input_sha256": {"reviewed_unreachable": digest},
                        "reviewed_unreachable": {"records": list(records.values()), "effective_cidrs": 1}}
            with patch.object(validation, "UNREACHABLE_PATH", path), patch.object(validation, "read_reviewed", return_value=records):
                self.assertEqual(validation.verify_unreachable_manifest(manifest, nets("192.0.2.0/25"), set(), set(), set()),
                                 nets("192.0.2.128/25"))
                path.write_text("tampered", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "provenance"):
                    validation.verify_unreachable_manifest(manifest, set(), set(), set(), set())
