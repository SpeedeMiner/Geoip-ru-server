import ipaddress
import json
import tempfile
import unittest
from pathlib import Path

from audit_v41_named_service_attribution import analyze, explain, named_services


class NamedServiceAttributionTests(unittest.TestCase):
    def make_catalog(self, services):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        path = Path(work.name) / "services.json"
        path.write_text(json.dumps({"categories": [{"id": "banking", "services": services}]}), encoding="utf-8")
        return path

    def row(self, ip, evidence, matched="kyoresuas-standard"):
        return {"prefix": ip, "evidence_sources": evidence, "service_matches": matched,
                "shared_prefix": "198.51.100.0/24"}

    def test_named_broad_overlapping_services_are_not_ip_ownership(self):
        records = named_services(self.make_catalog([
            {"name": "Bank A", "tier": "lite", "asns": [64501], "ipv4": ["198.51.100.0/24"]},
            {"name": "Bank B", "tier": "standard", "asns": [64502], "ipv4": ["198.51.100.0/25"]},
        ]))
        result, stats = analyze([self.row("198.51.100.7/32", "antifilter-ip.lst")], records)
        self.assertEqual(result[0]["named_service_count"], 2)
        self.assertEqual(result[0]["catalog_evidence_type"], "NAMED_BROAD_SHARED")
        self.assertEqual(result[0]["most_specific_named_prefix"], "198.51.100.0/25")
        self.assertEqual(result[0]["active_regulatory_block_verified"], "NO")
        self.assertEqual(stats["current_hard_rows"], 1)

    def test_exact_host_named_and_legacy_only_evidence(self):
        records = named_services(self.make_catalog([
            {"name": "Bank", "tier": "lite", "ipv4": ["203.0.113.7/32"]},
        ]))
        rows, stats = analyze([self.row("203.0.113.7/32", "v38-baseline-hard-or-unclassified")], records)
        self.assertEqual(rows[0]["catalog_evidence_type"], "NAMED_EXACT_HOST")
        self.assertEqual(rows[0]["evidence_priority"], "HISTORICAL_REVIEW")
        self.assertEqual(stats["named_exact_host_rows"], 1)

    def test_aggregate_only_and_other_service_source_kept_separate(self):
        records = named_services(self.make_catalog([
            {"name": "Unrelated", "tier": "lite", "ipv4": ["192.0.2.0/24"]},
        ]))
        rows, stats = analyze([
            self.row("198.51.100.2/32", "antifilter-ip.lst"),
            self.row("198.51.100.3/32", "antifilter-ip.lst", "operator-whitelist"),
        ], records)
        self.assertEqual(rows[0]["catalog_evidence_type"], "KYORE_SUAS_AGGREGATE_ONLY")
        self.assertEqual(rows[1]["catalog_evidence_type"], "OTHER_SERVICE_SOURCE")
        self.assertEqual(stats["named_catalog_rows"], 0)

    def test_disallow_default_route(self):
        with self.assertRaisesRegex(ValueError, "default-route"):
            named_services(self.make_catalog([
                {"name": "Unsafe", "tier": "lite", "ipv4": ["0.0.0.0/0"]},
            ]))


if __name__ == "__main__":
    unittest.main()
