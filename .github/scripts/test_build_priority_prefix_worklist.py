from __future__ import annotations
import csv
import tempfile
import unittest
from pathlib import Path
from build_priority_prefix_worklist import build_worklist

FIELDS = [
    "PREFIX", "FAMILY", "PRIORITY_REASON", "INCLUSION_BASIS", "GLOBAL_BGP_ORIGIN_ASNS",
    "RPKI_INVALID_ORIGINS", "RPKI_UNKNOWN_ORIGINS", "IRR_EXACT_ORIGINS",
    "IRR_ORIGIN_ASNS_NOT_IN_BGP", "BGP_ORIGIN_ASNS_WITHOUT_EXACT_IRR",
    "RDAP_SAMPLE_CONSISTENCY", "RDAP_COUNTRIES", "TRIAGE_FLAGS", "STATUS", "GLOBAL_BGP_MOAS",
]

def row(prefix, flags, status="REVIEW", basis="REGIONAL_RIR_ASN_ORIGIN+COMPANY_ASN"):
    return {
        "PREFIX": prefix, "FAMILY": "IPv6" if ":" in prefix else "IPv4",
        "PRIORITY_REASON": "TEST", "INCLUSION_BASIS": basis,
        "GLOBAL_BGP_ORIGIN_ASNS": "AS12345",
        "RPKI_INVALID_ORIGINS": "AS12345" if "RPKI_INVALID_ASN" in flags else "",
        "RPKI_UNKNOWN_ORIGINS": "AS12345" if "RPKI_UNKNOWN" in flags else "",
        "IRR_EXACT_ORIGINS": "AS12345", "IRR_ORIGIN_ASNS_NOT_IN_BGP": "",
        "BGP_ORIGIN_ASNS_WITHOUT_EXACT_IRR": "",
        "RDAP_SAMPLE_CONSISTENCY": "MULTIPLE_RESOURCE_OBJECTS_AT_SAMPLES" if "RDAP_MULTIPLE_SAMPLE_OBJECTS" in flags else "SAMPLED_RESOURCE_EXACT_PREFIX",
        "RDAP_COUNTRIES": "RU,TR" if "RDAP_COUNTRY_MIXED" in flags else "RU",
        "TRIAGE_FLAGS": flags, "STATUS": status,
        "GLOBAL_BGP_MOAS": "yes" if "MOAS" in flags else "no",
    }

class WorklistTests(unittest.TestCase):
    def build_inputs(self, root, rows, spots):
        evidence = root / "evidence"
        evidence.mkdir()
        with (evidence / "priority_prefix_triage.tsv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
            w.writeheader(); w.writerows(rows)
        if spots:
            with (evidence / "priority_prefix_external_spot_checks_v37.tsv").open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["PREFIX","STATUS","OBSERVED_PREFIXES","SUMMARY","SOURCE_URLS"], delimiter="\t", lineterminator="\n")
                w.writeheader(); w.writerows(spots)
        return evidence

    def test_review_order_tracks_and_external_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [
                row("198.51.100.0/24", "RPKI_INVALID_ASN | MOAS"),
                row("192.0.2.0/24", "IRR_NO_EXACT_OBJECT"),
                row("203.0.113.0/24", "RDAP_COUNTRY_MIXED | RDAP_MULTIPLE_SAMPLE_OBJECTS"),
                row("2001:db8::/48", "COMPANY_ONLY", basis="COMPANY_ASN_ONLY"),
                row("198.18.0.0/23", "MOAS"),
            ]
            spots = [
                {"PREFIX":"198.51.100.0/24","STATUS":"CHECKED_2026-11-11","OBSERVED_PREFIXES":"198.51.100.0/24","SUMMARY":"exact scope","SOURCE_URLS":"https://example.test/source"},
                {"PREFIX":"198.18.0.0/23","STATUS":"CHECKED_2026-11-10","OBSERVED_PREFIXES":"198.18.1.0/24","SUMMARY":"more-specific only; not the covering prefix","SOURCE_URLS":"https://example.test/more-specific"},
            ]
            evidence = self.build_inputs(root, rows, spots)
            out, stats = root/"worklist.tsv", root/"stats.txt"
            result = build_worklist(evidence, out, stats, expected_scope=None)
            with out.open(encoding="utf-8", newline="") as f:
                got = list(csv.DictReader((line for line in f if not line.startswith("#")), delimiter="\t"))
            self.assertEqual(result["rows"], 5)
            self.assertEqual([r["PREFIX"] for r in got], ["198.51.100.0/24","192.0.2.0/24","203.0.113.0/24","2001:db8::/48","198.18.0.0/23"])
            self.assertEqual(got[0]["PRIMARY_REVIEW_TRACK"], "RPKI_INVALID_ORIGIN_REVALIDATION")
            self.assertEqual(got[0]["EXTERNAL_SPOT_CHECK_STATUS"], "CHECKED_2026-11-11")
            self.assertEqual(got[0]["EXTERNAL_SPOT_CHECK_SCOPE_RELATION"], "EXACT_ONLY")
            self.assertEqual(got[4]["EXTERNAL_SPOT_CHECK_SCOPE_RELATION"], "MORE_SPECIFIC_ONLY")
            self.assertTrue(all(r["STATUS"] == "REVIEW" for r in got))
            self.assertIn("no row is approved", stats.read_text(encoding="utf-8"))

    def test_rejects_invalid_spot_check_calendar_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            spots=[{"PREFIX":"192.0.2.0/24","STATUS":"CHECKED_2026-02-30","OBSERVED_PREFIXES":"192.0.2.0/24","SUMMARY":"bad date","SOURCE_URLS":"https://example.test/source"}]
            evidence=self.build_inputs(root,[row("192.0.2.0/24","MOAS")],spots)
            with self.assertRaisesRegex(ValueError,"invalid or undated"):
                build_worklist(evidence,root/"out.tsv",root/"stats.txt",expected_scope=None)

    def test_rejects_non_review_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            evidence=self.build_inputs(root,[row("192.0.2.0/24","MOAS",status="APPROVED")],[])
            with self.assertRaisesRegex(ValueError,"non-REVIEW"):
                build_worklist(evidence,root/"out.tsv",root/"stats.txt",expected_scope=None)

    def test_rejects_unrelated_spot_checked_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            spots=[{"PREFIX":"192.0.2.0/24","STATUS":"CHECKED_2026-11-10","OBSERVED_PREFIXES":"198.51.100.0/24","SUMMARY":"wrong scope","SOURCE_URLS":"https://example.test/source"}]
            evidence=self.build_inputs(root,[row("192.0.2.0/24","MOAS")],spots)
            with self.assertRaisesRegex(ValueError,"unrelated"):
                build_worklist(evidence,root/"out.tsv",root/"stats.txt",expected_scope=None)

if __name__ == "__main__":
    unittest.main()
