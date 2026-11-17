from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import validate_v41_service_inventory as inventory


class ServiceInventoryTests(unittest.TestCase):
    def test_domain_evidence_does_not_assert_ip_or_whitelist_membership(self):
        path = Path(__file__).resolve().parent.parent / "data" / "v41-service-inventory.tsv"
        rows = inventory.read_inventory(path)
        self.assertGreaterEqual(len(rows), 3)
        self.assertTrue(all(row["asn_or_cidr"] == "-" for row in rows))
        self.assertIn("no claim of Ministry whitelist membership", inventory.format_report(rows))

    def test_rejects_duplicates_future_dates_and_unverified_ip_claim(self):
        header = "\t".join(inventory.HEADER) + "\n"
        row = "Example\texample.org\t-\tOFFICIAL_DOMAIN\t2026-11-16\thttps://example.org/about\tLOCAL_CRITICAL\tDOMAIN_REVIEW\n"
        with TemporaryDirectory() as folder:
            path = Path(folder) / "inventory.tsv"
            for body in (row + row, row.replace("2026-11-16", "2026-11-17"), row.replace("\t-\t", "\tAS123\t"),
                         row.replace("example.org\t-", "*.example.org\t-")):
                path.write_text(header + body, encoding="utf-8")
                with self.assertRaises(ValueError):
                    inventory.read_inventory(path, as_of=date(2026, 11, 16))
