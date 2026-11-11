import csv
import tempfile
import unittest
from pathlib import Path

from build_priority_prefix_triage import build_triage


def write_tsv(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class PriorityPrefixTriageTests(unittest.TestCase):
    def _fixture(self, root: Path, bad_status: bool = False):
        priority = [
            {"PREFIX":"198.51.100.0/24","FAMILY":"IPv4","COMPANY_ASNS":"AS1","GLOBAL_BGP_ORIGIN_ASNS":"AS1,AS2","GLOBAL_BGP_MOAS":"yes","INCLUSION_BASIS":"REGIONAL_RIR_ASN_ORIGIN+COMPANY_ASN","PRIORITY_REASON":"EXACT_MOAS","STATUS":"APPROVED" if bad_status else "REVIEW"},
            {"PREFIX":"203.0.113.0/24","FAMILY":"IPv4","COMPANY_ASNS":"AS3","GLOBAL_BGP_ORIGIN_ASNS":"AS3","GLOBAL_BGP_MOAS":"no","INCLUSION_BASIS":"COMPANY_ASN_ONLY","PRIORITY_REASON":"COMPANY_ONLY","STATUS":"REVIEW"},
        ]
        holder = [
            {"PREFIX":"198.51.100.0/24","GLOBAL_BGP_ORIGIN_ASNS":"AS1,AS2","STATUS":"REVIEW","RDAP_SAMPLE_COUNT":"3","RDAP_SUCCESS_COUNT":"3","RDAP_SAMPLE_CONSISTENCY":"MULTIPLE_RESOURCE_OBJECTS_AT_SAMPLES","RDAP_RESOURCE_HANDLES":"NET-A | NET-B","RDAP_REGISTRANT_ENTITIES":"A LLC | B LLC","RDAP_COUNTRIES":"RU,FI","RDAP_REGISTERED_CIDRS":"198.51.100.0/25 | 198.51.100.128/25","RDAP_QUERY_ERRORS":""},
            {"PREFIX":"203.0.113.0/24","GLOBAL_BGP_ORIGIN_ASNS":"AS3","STATUS":"REVIEW","RDAP_SAMPLE_COUNT":"3","RDAP_SUCCESS_COUNT":"3","RDAP_SAMPLE_CONSISTENCY":"SAMPLED_RESOURCE_EXACT_PREFIX","RDAP_RESOURCE_HANDLES":"NET-C","RDAP_REGISTRANT_ENTITIES":"C LLC","RDAP_COUNTRIES":"TR","RDAP_REGISTERED_CIDRS":"203.0.113.0/24","RDAP_QUERY_ERRORS":""},
        ]
        rpki = [
            {"PREFIX":"198.51.100.0/24","ORIGIN_ASN":"AS1","QUERY_STATUS":"OK","RPKI_STATUS":"invalid_asn"},
            {"PREFIX":"198.51.100.0/24","ORIGIN_ASN":"AS2","QUERY_STATUS":"OK","RPKI_STATUS":"valid"},
            {"PREFIX":"203.0.113.0/24","ORIGIN_ASN":"AS3","QUERY_STATUS":"OK","RPKI_STATUS":"unknown"},
        ]
        irr = [
            {"PREFIX":"198.51.100.0/24","QUERY_STATUS":"OK","IRR_UNIQUE_ROUTE_OBJECTS":"1","IRR_EXACT_OBJECTS":"1","IRR_EXACT_BGP_ORIGIN_MATCH_OBJECTS":"1","IRR_EXACT_ORIGINS":"AS1","IRR_MATCHED_BGP_ORIGINS":"AS1","STATUS":"REVIEW"},
            {"PREFIX":"203.0.113.0/24","QUERY_STATUS":"NO_OBJECTS_IN_QUERIED_SOURCES","IRR_UNIQUE_ROUTE_OBJECTS":"0","IRR_EXACT_OBJECTS":"0","IRR_EXACT_BGP_ORIGIN_MATCH_OBJECTS":"0","IRR_EXACT_ORIGINS":"","IRR_MATCHED_BGP_ORIGINS":"","STATUS":"REVIEW"},
        ]
        objects = [
            {"QUERY_PREFIX":"198.51.100.0/24","OBJECT_TYPE":"route","ROUTE_PREFIX":"198.51.100.0/24","ORIGIN_ASN":"AS1","EXACT_PREFIX_MATCH":"yes","GLOBAL_BGP_ORIGIN_MATCH":"yes"},
        ]
        for name, rows in [
            ("priority_prefixes.tsv", priority),
            ("prefix_holder_review_summary.tsv", holder),
            ("rpki_by_origin.tsv", rpki),
            ("irr_prefix_summary.tsv", irr),
            ("irr_route_objects_deduplicated.tsv", objects),
        ]:
            write_tsv(root / name, rows)

    def test_flags_are_recomputed_from_rdap_rpki_and_deduplicated_irr(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root)
            output, stats = root / "triage.tsv", root / "stats.txt"
            result = build_triage(root, output, stats, expected_scope=(2, 1, 1))
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(
                    (line for line in stream if not line.startswith("#")), delimiter="\t"
                ))
            self.assertEqual(result["rows"], 2)
            first, second = rows
            self.assertEqual(set(first["TRIAGE_FLAGS"].split(" | ")), {
                "RPKI_INVALID_ASN", "IRR_ORIGIN_SET_DIFFERS_FROM_BGP",
                "RDAP_MULTIPLE_SAMPLE_OBJECTS", "RDAP_COUNTRY_MIXED", "MOAS",
            })
            self.assertEqual(set(second["TRIAGE_FLAGS"].split(" | ")), {
                "RPKI_UNKNOWN", "IRR_NO_EXACT_OBJECT", "COMPANY_ONLY",
            })
            self.assertEqual(first["IRR_ORIGIN_ASNS_NOT_IN_BGP"], "")
            self.assertEqual(first["BGP_ORIGIN_ASNS_WITHOUT_EXACT_IRR"], "AS2")
            self.assertTrue(all(row["STATUS"] == "REVIEW" for row in rows))
            self.assertIn("no row is automatically approved", stats.read_text(encoding="utf-8"))

    def test_default_scope_tracks_current_inventory_without_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root)
            output, stats = root / "out.tsv", root / "stats.txt"
            result = build_triage(root, output, stats)
            self.assertEqual(result["rows"], 2)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(
                    (line for line in stream if not line.startswith("#")), delimiter="\\t"
                ))
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row["STATUS"] == "REVIEW" for row in rows))
            self.assertIn("Priority prefixes: 2", stats.read_text(encoding="utf-8"))

    def test_scope_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root)
            with self.assertRaisesRegex(ValueError, "priority scope changed"):
                build_triage(root, root / "out.tsv", root / "stats.txt", expected_scope=(56, 52, 4))

    def test_non_review_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root, bad_status=True)
            with self.assertRaisesRegex(ValueError, "priority row is not REVIEW"):
                build_triage(root, root / "out.tsv", root / "stats.txt", expected_scope=(2, 1, 1))


if __name__ == "__main__":
    unittest.main()
