import io
import ipaddress
import json
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
import unittest

from audit_v41_asn_regressions import (
    ARCHIVE, compare, read_observed, read_selected, read_watchlist,
    summarize_impact, summarize_observed_changes, write_summary,
)
from build_v41_overlay import intervals
from v41_asn_observations import parse_announced_prefixes

NET = ipaddress.ip_network
WATCH = {123: {"group": "test", "entity": "test origin", "evidence": "https://example.test"}}


class PriorityASNTests(unittest.TestCase):
    def test_summary_never_treats_a_missing_baseline_as_zero_loss(self):
        candidate = {"observed": {}, "selected": ({}, {}), "direct": {4: [], 6: []}}
        rows = compare(WATCH, None, candidate)
        report = {"rows": rows, "previous_release": None,
                  "direct_impact_summary": summarize_impact(rows),
                  "observed_snapshot_identity": {"status": "NO_VERIFIED_BASELINE"}}
        out = io.StringIO()
        write_summary(report, out)
        self.assertIn("coverage changes are unknown", out.getvalue())
        self.assertNotIn("lost from final DIRECT: 0", out.getvalue())

    def test_invalid_default_wrong_family_and_normalization_keep_extraction_semantics(self):
        rows, rejected, normalized = parse_announced_prefixes({
            "ipv4": ["192.0.2.4/24", "2001:db8::1", "198.51.100.7/0"],
            "ipv6": ["invalid", "2001:db8::/48"],
        })
        self.assertEqual(rows, [("ipv4", NET("192.0.2.0/24")), ("ipv6", NET("2001:db8::/48"))])
        self.assertEqual((rejected, normalized), (3, 1))

    def test_lost_vs_rejected_family_and_static_pin(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            archive = path / "example.tar.gz"
            selected = path / "selected.txt"
            selected.write_text("2001:db8::/48 # AS123[RIR-RU][STATIC-DIRECT],AS456[RIR-BY/KZ]\n")
            def snapshot(prefixes):
                with tarfile.open(archive, "w:gz") as tar:
                    body = json.dumps({"asn": 123, "prefixes": prefixes}).encode()
                    item = tarfile.TarInfo("root/as/123/aggregated.json")
                    item.size = len(body)
                    tar.addfile(item, io.BytesIO(body))
                return {"observed": read_observed(archive, WATCH),
                        "selected": read_selected(selected, WATCH), "direct": {4: [], 6: []}}
            before = snapshot({"ipv6": ["2001:db8::/48"]})
            empty = snapshot({"ipv6": []})
            bad = snapshot({"ipv6": ["2001:db8::/129", "192.0.2.0/24", "::/0"]})
            lost, rejected = [compare(WATCH, before, candidate)[1] for candidate in (empty, bad)]
            self.assertEqual(lost["candidate"]["observation"], "FAMILY_NOT_OBSERVED")
            self.assertEqual(rejected["candidate"]["observation"], "NO_VALID_PREFIX_AFTER_REJECTION")
            self.assertIn("PREVIOUSLY_OBSERVED_FAMILY_LOST", lost["review_reasons"])
            self.assertIn("PARSER_REJECTED_RECORDS", rejected["review_reasons"])
            self.assertNotIn("PARSER_REJECTED_RECORDS", lost["review_reasons"])
            self.assertEqual(rejected["candidate"]["layers"]["static_selected_pins"]["addresses"], str(2**80))
            self.assertEqual(rejected["delta"]["observed"]["removed"]["cidrs"], ["2001:db8::/48"])
            self.assertEqual(rejected["delta"]["selected"]["removed"]["addresses"], "0")

    def test_moas_attribution_keeps_every_watched_origin(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "origin.txt"
            p.write_text("192.0.2.0/24 # AS123[A],AS456[RIR-RU+Company]\n")
            selected, pins = read_selected(p, {123, 456})
            self.assertEqual(dict(selected), {(123, 4): {NET("192.0.2.0/24")}, (456, 4): {NET("192.0.2.0/24")}})
            self.assertFalse(pins)

    def test_checked_in_watchlist_is_report_only_and_includes_priority_groups(self):
        path = Path(__file__).resolve().parents[1] / "data/v41-audit-priority-asns.tsv"
        entries = read_watchlist(path)
        self.assertTrue({13238, 47541, 44386, 49053, 35673, 6697, 9198, 35237} <= entries.keys())


    def test_loss_is_split_against_the_final_dat_for_both_families(self):
        for version, (whole, keep, lost) in {
            4: ("192.0.2.0/24", "192.0.2.0/25", "192.0.2.128/25"),
            6: ("2001:db8::/48", "2001:db8::/49", "2001:db8:0:8000::/49"),
        }.items():
            with self.subTest(version=version):
                before = {"observed": {}, "selected": ({(123, version): {NET(whole)}}, {}),
                          "direct": {**{4: [], 6: []}, version: intervals([NET(whole)], version)}}
                candidate = {"observed": {}, "selected": ({}, {}),
                             "direct": {**{4: [], 6: []}, version: intervals([NET(keep)], version)}}
                rows = compare(WATCH, before, candidate)
                row = rows[0 if version == 4 else 1]
                impact = row["previous_selected_direct_impact"]
                self.assertEqual(impact["retained_in_final_direct"]["cidrs"], [keep])
                self.assertEqual(impact["removed_from_final_direct"]["cidrs"], [lost])
                self.assertEqual(sum(int(v["addresses"]) for v in impact.values()), NET(whole).num_addresses)
                self.assertEqual(summarize_impact(rows)["affected_pairs"],
                                 {"attribution_loss_direct_retained": 1, "space_lost_from_final_direct": 1})

    def test_no_baseline_is_unknown_and_unrelated_loss_is_not_attributed(self):
        net = NET("192.0.2.0/24")
        before = {"observed": {}, "selected": ({}, {}),
                  "direct": {4: intervals([net], 4), 6: []}}
        after = {"observed": {}, "selected": ({}, {}), "direct": {4: [], 6: []}}
        rows = compare(WATCH, None, after)
        self.assertIsNone(rows[0]["previous_selected_direct_impact"])
        self.assertFalse(summarize_impact(rows)["baseline_available"])
        self.assertIsNone(summarize_impact(rows)["affected_pairs"])
        rows = compare(WATCH, before, after)
        self.assertEqual(rows[0]["previous_selected_direct_impact"]["removed_from_final_direct"]["cidrs"], [])
        self.assertNotIn("PREVIOUS_ASN_SELECTED_SPACE_LOST_FROM_FINAL_DIRECT", rows[0]["review_reasons"])

    def test_final_direct_loss_can_happen_without_losing_asn_selection(self):
        n = NET("192.0.2.0/24")
        before = {"observed": {}, "selected": ({(123, 4): {n}}, {}),
                  "direct": {4: intervals([n], 4), 6: []}}
        after = {**before, "direct": {4: [], 6: []}}
        row = compare(WATCH, before, after)[0]
        self.assertEqual(row["delta"]["selected"]["removed"]["addresses"], "0")
        self.assertEqual(row["previous_selected_direct_impact"]["removed_from_final_direct"]["cidrs"], [str(n)])
        self.assertNotIn("ASN_ATTRIBUTION_LOSS_DIRECT_RETAINED", row["review_reasons"])


    @staticmethod
    def observed_fixture(label, *nets, asn=123, version=4):
        return {"hashes": {ARCHIVE: label}, "observed": {
            asn: {version: ({NET(n) for n in nets}, {}, [], "fixture")},
        }}

    def test_repacked_archive_does_not_count_as_new_watched_input(self):
        old = self.observed_fixture("before", "192.0.2.0/25", "192.0.2.128/25")
        new = self.observed_fixture("after", "192.0.2.128/25", "192.0.2.0/25")
        result = summarize_observed_changes(WATCH, old, new)
        self.assertEqual(result["status"], "DIFFERENT_ARCHIVE_SAME_WATCHED_PREFIXES")
        self.assertEqual(result["previous"], result["candidate"])
        self.assertEqual(result["changed_address_space_pairs"], 0)
        self.assertEqual(summarize_observed_changes(WATCH, old, old)["status"], "IDENTICAL_ARCHIVE")
        unknown = summarize_observed_changes(WATCH, None, new)
        self.assertIsNone(unknown["previous"])
        self.assertIsNone(unknown["changed_address_space_pairs"])

    def test_deaggregation_separates_prefix_changes_from_address_changes(self):
        old = self.observed_fixture("before", "2001:db8::/48", version=6)
        new = self.observed_fixture("after", "2001:db8::/49", "2001:db8:0:8000::/49", version=6)
        result = summarize_observed_changes(WATCH, old, new)
        self.assertEqual(result["status"], "WATCHED_PREFIX_SHAPE_CHANGED_WITHOUT_ADDRESS_CHANGE")
        self.assertEqual((result["changed_prefix_pairs"], result["changed_address_space_pairs"]), (1, 0))
        self.assertNotEqual(result["previous"]["normalized_prefix_sha256"], result["candidate"]["normalized_prefix_sha256"])
        self.assertEqual(result["previous"]["normalized_address_union_sha256"], result["candidate"]["normalized_address_union_sha256"])

    def test_origin_changes_are_not_hidden_by_equal_global_address_space(self):
        watch = {**WATCH, 456: {**WATCH[123]}}
        old = self.observed_fixture("before", "192.0.2.0/24")
        new = self.observed_fixture("after", "192.0.2.0/24", asn=456)
        result = summarize_observed_changes(watch, old, new)
        self.assertEqual(result["status"], "WATCHED_ADDRESS_SPACE_CHANGED")
        self.assertEqual(result["changed_address_space_pairs"], 2)
