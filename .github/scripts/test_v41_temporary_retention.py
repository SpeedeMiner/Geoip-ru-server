import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_v41_overlay import (
    intervals, read_temporary_retention, require_temporary_retention, subtract_networks,
    temporary_retention_manifest, verify_temporary_retention_manifest,
)


class TemporaryRetentionTests(unittest.TestCase):
    baseline = "63b8abf0ba6c2264724a58ec9a2fb7035c5130a6"
    header = "prefix\tprevious_release\treview_on\n"

    def load_rows(self, rows):
        with TemporaryDirectory() as folder:
            test_registry = Path(folder) / "retention.tsv"
            test_registry.write_text(self.header + rows, encoding="utf-8")
            return read_temporary_retention(test_registry)

    def row(self, prefix, review="2026-12-17", sha=None):
        return f"{prefix}\t{sha or self.baseline}\t{review}\n"

    def test_incident_registry_contains_only_the_six_exact_routes(self):
        path = Path(__file__).resolve().parent.parent / "data/v41-temporary-release-retention.tsv"
        records = read_temporary_retention(path)
        self.assertEqual(set(map(str, records)), {
            "156.224.80.0/24", "156.241.186.0/24", "177.29.246.0/24",
            "177.122.107.0/24", "177.122.160.0/24", "177.166.21.0/24",
        })
        self.assertEqual({x["previous_release"] for x in records.values()}, {self.baseline})

    def test_no_broader_network_or_private_network(self):
        for prefix in ("31.204.32.0/20", "192.168.1.0/24", "224.0.2.0/24", "2001:4860::/48", "156.224.80.1/24"):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                self.load_rows(self.row(prefix))

    def test_empty_duplicate_or_bad_provenance(self):
        good = self.row("156.224.80.0/24")
        for invalid in ("", good + good, self.row("156.224.80.0/24", sha="abcdef"),
                        self.row("156.224.80.0/24", review="20261217"),
                        "156.224.80.0/24\n", good.rstrip() + "\textra\n"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.load_rows(invalid)

    def test_review_date_does_not_auto_remove(self):
        records = self.load_rows(self.row("156.224.80.0/24", review="2020-01-01"))
        require_temporary_retention(records, intervals(records, 4))
        with self.assertRaisesRegex(ValueError, "requires review"):
            require_temporary_retention(records, [])

    def test_coverage_accepts_split_representation(self):
        records = self.load_rows(self.row("156.224.80.0/24"))
        target = next(iter(records))
        require_temporary_retention(records, intervals(set(target.subnets()), 4))

    def test_manifest_binds_registry_and_requires_the_input(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / "retention.tsv"
            p.write_text(self.header + self.row("156.224.80.0/24"), encoding="utf-8")
            r = read_temporary_retention(p)
            manifest = {"temporary_release_retention": temporary_retention_manifest(p, r)}
            self.assertEqual(verify_temporary_retention_manifest(p, manifest), r)
            with self.assertRaisesRegex(ValueError, "no matching registry"):
                verify_temporary_retention_manifest(None, manifest)
            p.write_text(self.header + self.row("156.224.80.0/24", review="2026-12-18"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                verify_temporary_retention_manifest(p, manifest)

    def test_effective_exclusions_hold_instead_of_force_routing(self):
        records = self.load_rows(self.row("156.224.80.0/24"))
        blocked = ipaddress.ip_network("156.224.80.5/32")
        remaining = subtract_networks(set(records), {blocked})
        self.assertEqual(sum(net.num_addresses for net in remaining), 255)
        with self.assertRaisesRegex(ValueError, "156.224.80.0/24"):
            require_temporary_retention(records, intervals(remaining, 4))


if __name__ == "__main__":
    unittest.main()
