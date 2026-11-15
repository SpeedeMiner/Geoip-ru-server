from __future__ import annotations
import csv
import tempfile
import unittest
from pathlib import Path
from build_priority_rpki_reconciliation import build_reconciliation

class ReconciliationTests(unittest.TestCase):
    def write(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter="\t",lineterminator="\n")
            w.writeheader(); w.writerows(rows)

    def setup_inputs(self, root):
        evidence=root/"evidence"; evidence.mkdir()
        triage=[
            {"PREFIX":"192.0.2.0/24","GLOBAL_BGP_ORIGIN_ASNS":"AS12345|AS23456",
             "RPKI_INVALID_ORIGINS":"AS12345","TRIAGE_FLAGS":"RPKI_INVALID_ASN | MOAS","STATUS":"REVIEW"},
            {"PREFIX":"198.51.100.0/24","GLOBAL_BGP_ORIGIN_ASNS":"AS34567",
             "RPKI_INVALID_ORIGINS":"AS34567","TRIAGE_FLAGS":"RPKI_INVALID_ASN","STATUS":"REVIEW"},
        ]
        worklist=[
            {"PREFIX":"192.0.2.0/24","EXTERNAL_SPOT_CHECK_STATUS":"CHECKED_2026-11-10",
             "EXTERNAL_SPOT_CHECK_SCOPE_RELATION":"EXACT_AND_MORE_SPECIFIC","STATUS":"REVIEW"},
            {"PREFIX":"198.51.100.0/24","EXTERNAL_SPOT_CHECK_STATUS":"CHECKED_2026-11-10",
             "EXTERNAL_SPOT_CHECK_SCOPE_RELATION":"MORE_SPECIFIC_ONLY","STATUS":"REVIEW"},
        ]
        spots=[
            {"PREFIX":"192.0.2.0/24","STATUS":"CHECKED_2026-11-10",
             "OBSERVED_PREFIXES":"192.0.2.0/24 | 192.0.2.0/25","SUMMARY":"exact MOAS note",
             "SOURCE_URLS":"https://example.test/192"},
            {"PREFIX":"198.51.100.0/24","STATUS":"CHECKED_2026-11-10",
             "OBSERVED_PREFIXES":"198.51.100.0/25","SUMMARY":"child-only note",
             "SOURCE_URLS":"https://example.test/198"},
        ]
        rpki=[
            {"PREFIX":"192.0.2.0/24","ORIGIN_ASN":"AS12345","QUERY_STATUS":"OK","RPKI_STATUS":"invalid_asn"},
            {"PREFIX":"198.51.100.0/24","ORIGIN_ASN":"AS34567","QUERY_STATUS":"OK","RPKI_STATUS":"invalid_asn"},
        ]
        seed=[
            {"PREFIX":"192.0.2.0/24","EXTERNAL_EXACT_ORIGIN_ASNS":"AS23456",
             "EXTERNAL_EXACT_RPKI_STATUS":"AS23456:valid",
             "RECONCILIATION_CLASS":"EXACT_ORIGIN_SET_CHANGED",
             "ASSESSMENT":"Archive origin absent from exact external set",
             "REQUIRED_NEXT_ACTION":"Refresh exact RIB and VRPs.","ARCHIVED_INVALID_RPKI_ORIGINS":"AS12345"},
            {"PREFIX":"198.51.100.0/24","EXTERNAL_EXACT_ORIGIN_ASNS":"",
             "EXTERNAL_EXACT_RPKI_STATUS":"NOT_CHECKED",
             "RECONCILIATION_CLASS":"MORE_SPECIFIC_ONLY_NO_EXACT_VERDICT",
             "ASSESSMENT":"Only a child route was checked",
             "REQUIRED_NEXT_ACTION":"Refresh exact RIB and VRPs.","ARCHIVED_INVALID_RPKI_ORIGINS":"AS34567"},
        ]
        self.write(evidence/"priority_prefix_triage.tsv",triage)
        self.write(evidence/"priority_prefix_review_worklist.tsv",worklist)
        self.write(evidence/"priority_prefix_external_spot_checks_v37.tsv",spots)
        self.write(evidence/"rpki_by_origin.tsv",rpki)
        seed_path=root/"seed.tsv"; self.write(seed_path,seed)
        return evidence,seed_path

    def test_joins_exact_and_more_specific_scope_without_promoting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); evidence,seed=self.setup_inputs(root)
            out=root/"out.tsv"; stats=root/"stats.txt"
            result=build_reconciliation(evidence,seed,out,stats,expected_count=2)
            with out.open(encoding="utf-8",newline="") as f:
                rows=list(csv.DictReader((l for l in f if not l.startswith("#")),delimiter="\t"))
            self.assertEqual(result["rows"],2)
            self.assertEqual(result["unseeded_pairs"], 0)
            by={r["PREFIX"]:r for r in rows}
            self.assertEqual(by["192.0.2.0/24"]["EXTERNAL_NLRI_SCOPE_RELATION"],"EXACT_AND_MORE_SPECIFIC")
            self.assertEqual(by["192.0.2.0/24"]["EXTERNAL_EXACT_ORIGIN_ASNS"],"AS23456")
            self.assertEqual(by["198.51.100.0/24"]["EXTERNAL_NLRI_SCOPE_RELATION"],"MORE_SPECIFIC_ONLY")
            self.assertEqual(by["198.51.100.0/24"]["EXTERNAL_EXACT_ORIGIN_ASNS"],"")
            self.assertTrue(all(r["STATUS"]=="REVIEW" for r in rows))
            self.assertIn("synchronized full-RIB",stats.read_text(encoding="utf-8"))

    def test_routes_new_prefix_and_new_origin_on_historical_prefix_to_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, seed = self.setup_inputs(root)
            extra = "203.0.113.0/24"
            path = evidence / "priority_prefix_triage.tsv"
            body = path.read_text().replace("AS12345\tRPKI_INVALID_ASN", "AS12345|AS23456\tRPKI_INVALID_ASN")
            path.write_text(body + f"{extra}\tAS45678\tAS45678\tRPKI_INVALID_ASN\tREVIEW\n")
            with (evidence / "priority_prefix_review_worklist.tsv").open("a") as f:
                f.write(f"{extra}\tNOT_SPOT_CHECKED\t\tREVIEW\n")
            path = evidence / "rpki_by_origin.tsv"
            with path.open(newline="") as f:
                rows = list(csv.DictReader(f, delimiter="\t"))
            for row in rows:
                row["RPKI_URL"] = "https://example.test/rpki"
            rows.extend({"PREFIX": prefix, "ORIGIN_ASN": origin, "QUERY_STATUS": "OK",
                         "RPKI_STATUS": "invalid_asn", "RPKI_URL": "https://example.test/rpki"}
                        for prefix, origin in (("192.0.2.0/24", "AS23456"), (extra, "AS45678")))
            self.write(path, rows)
            out = root / "historical.tsv"
            result = build_reconciliation(evidence, seed, out, root / "stats.txt", expected_count=2)
            self.assertEqual((result["rows"], result["unseeded_pairs"]), (2, 2))
            with (root / "unseeded_rpki_invalid_review.tsv").open() as f:
                queued = list(csv.DictReader(f, delimiter="\t"))
            self.assertEqual([(r["PREFIX"], r["ORIGIN_ASN"]) for r in queued],
                             [("192.0.2.0/24", "AS23456"), (extra, "AS45678")])
            self.assertTrue(all(r["STATUS"] == "REVIEW" and
                                r["RECONCILIATION_CLASS"] == "UNSEEDED_CURRENT_RPKI_INVALID_NEEDS_SPOT_CHECK"
                                for r in queued))
            # A new invalid origin cannot stand in for a historical origin on the same prefix.
            rows[0]["RPKI_STATUS"] = "valid"
            self.write(path, rows)
            with self.assertRaisesRegex(ValueError, "archived invalid RPKI pair missing or changed.*AS12345"):
                build_reconciliation(evidence, seed, out, root / "stats.txt", expected_count=2)

    def test_rejects_missing_archived_invalid_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); evidence,seed=self.setup_inputs(root)
            p=evidence/"rpki_by_origin.tsv"
            self.write(p,[{"PREFIX":"198.51.100.0/24","ORIGIN_ASN":"AS34567","QUERY_STATUS":"OK","RPKI_STATUS":"valid"}])
            with self.assertRaisesRegex(ValueError,"archived invalid RPKI pair missing"):
                build_reconciliation(evidence,seed,root/"out.tsv",root/"stats.txt",expected_count=2)

    def test_rejects_seed_scope_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); evidence,seed=self.setup_inputs(root)
            self.write(seed,[{"PREFIX":"192.0.2.0/24","EXTERNAL_EXACT_ORIGIN_ASNS":"AS23456",
                              "EXTERNAL_EXACT_RPKI_STATUS":"AS23456:valid",
                              "RECONCILIATION_CLASS":"EXACT_ORIGIN_SET_CHANGED",
                              "ASSESSMENT":"x","REQUIRED_NEXT_ACTION":"y"}])
            with self.assertRaisesRegex(ValueError,"archived invalid seed scope changed"):
                build_reconciliation(evidence,seed,root/"out.tsv",root/"stats.txt",expected_count=2)

if __name__=="__main__":
    unittest.main()
