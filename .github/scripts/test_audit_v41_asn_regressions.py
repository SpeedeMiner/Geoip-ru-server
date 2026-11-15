import io
import ipaddress
import json
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
import unittest

from audit_v41_asn_regressions import compare, read_observed, read_selected, read_watchlist
from v41_asn_observations import parse_announced_prefixes

NET = ipaddress.ip_network
WATCH = {123: {"group": "test", "entity": "test origin", "evidence": "https://example.test"}}


class PriorityASNTests(unittest.TestCase):
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
