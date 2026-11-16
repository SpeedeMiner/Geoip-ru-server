import io
import ipaddress
import json
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import check_v41_bgp_observations as check


class BGPObservationTests(unittest.TestCase):
    def test_partial_window_is_preserved_in_json_and_summary(self):
        from datetime import timedelta
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output, summary = root / "report.json", root / "summary.md"
            empty = {4: set(), 6: set()}
            def ris(asn, start, end):
                return empty, {"query_starttime": start.isoformat(),
                               "query_endtime": (end - timedelta(hours=12)).isoformat(),
                               "latest_time": end.isoformat()}
            args = ["check", "--archive", "unused", "--asns", "123", "--output", str(output), "--summary", str(summary)]
            with patch.object(sys, "argv", args), patch.object(check, "read_ipverse", return_value={123: empty}), \
                    patch.object(check, "get_ris", side_effect=ris):
                check.main()
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["asns"]["AS123"]["status"], "partial-window")
            self.assertIn("| AS123 | partial-window |", summary.read_text(encoding="utf-8"))

    def test_shortened_ripe_window_is_labeled(self):
        from datetime import datetime, timedelta, timezone
        end = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
        metadata = {"query_starttime": "2026-11-15T12:00:00", "query_endtime": "2026-11-16T00:00:00"}
        self.assertEqual(check.window_status(metadata, end - timedelta(days=1), end), "partial-window")
        metadata["query_endtime"] = "2026-11-16T12:00:00"
        self.assertEqual(check.window_status(metadata, end - timedelta(days=1), end), "ok")

    def test_missing_family_is_not_mistaken_for_an_empty_observation(self):
        with self.assertRaisesRegex(ValueError, "invalid ipverse ipv6"):
            check.parse_families({"ipv4": ["192.0.2.0/24"]})
        self.assertEqual(check.parse_families({"ipv4": [], "ipv6": []}), {4: set(), 6: set()})

    def test_compares_address_space_not_cidr_spelling(self):
        old = {4: {ipaddress.ip_network("192.0.2.0/24")}, 6: {ipaddress.ip_network("2001:db8::/127")}}
        ris = {4: {ipaddress.ip_network("192.0.2.0/25")}, 6: {ipaddress.ip_network("2001:db8::/127")}}
        result = check.compare(old, ris)
        self.assertEqual(result["ipv4"]["ipverse_only_prefixes"], ["192.0.2.128/25"])
        self.assertEqual(result["ipv4"]["ris_only_addresses"], "0")
        self.assertEqual(result["ipv6"]["ipverse_only_addresses"], "0")

    def test_archive_selects_only_requested_asn_and_rejects_duplicate(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sample.tar.gz"
            payload = json.dumps({"asn": 123, "prefixes": {"ipv4": ["192.0.2.0/24"], "ipv6": []}}).encode()
            def archive(count):
                with tarfile.open(path, "w:gz") as stream:
                    for _ in range(count):
                        member = tarfile.TarInfo("test/as/123/aggregated.json")
                        member.size = len(payload)
                        stream.addfile(member, io.BytesIO(payload))
            archive(1)
            self.assertEqual(set(check.read_ipverse(path, {123})), {123})
            self.assertEqual(check.read_ipverse(path, {124}), {})
            archive(2)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                check.read_ipverse(path, {123})

    def test_ris_failure_is_not_mistaken_for_empty_observations(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return b'{"status":"error","data":{"prefixes":[]}}'
        with patch.object(check, "urlopen", return_value=Response()):
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            with self.assertRaisesRegex(ValueError, "RIPEstat error"):
                check.get_ris(123, now, now)

    def test_ris_parses_both_families_and_time_metadata(self):
        from datetime import datetime, timedelta, timezone
        now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        document = {"status": "ok", "data": {"resource": "123", "query_starttime": "2026-11-15T00:00:00",
                    "query_endtime": "2026-11-16T00:00:00", "latest_time": "2026-11-16T00:00:00",
                    "prefixes": [{"prefix": "192.0.2.0/24", "timelines": [{"starttime": "2026-11-15T00:00:00", "endtime": "2026-11-16T00:00:00"}]},
                                 {"prefix": "2001:db8::/48", "timelines": [{"starttime": "2026-11-15T00:00:00", "endtime": "2026-11-16T00:00:00"}]}]}}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return json.dumps(document).encode()
        with patch.object(check, "urlopen", return_value=Response()):
            families, metadata = check.get_ris(123, now - timedelta(days=1), now)
        self.assertEqual(families[4], {ipaddress.ip_network("192.0.2.0/24")})
        self.assertEqual(families[6], {ipaddress.ip_network("2001:db8::/48")})
        self.assertEqual(metadata["query_endtime"], "2026-11-16T00:00:00")

    def test_ris_stale_data_is_unavailable_not_a_route_loss(self):
        from datetime import datetime, timedelta, timezone
        now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        payload = {"status": "ok", "data": {"resource": "123", "query_starttime": "2026-11-10T00:00:00",
                   "query_endtime": "2026-11-16T00:00:00", "latest_time": "2026-11-10T00:00:00", "prefixes": []}}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return json.dumps(payload).encode()
        with patch.object(check, "urlopen", return_value=Response()):
            with self.assertRaisesRegex(ValueError, "stale"):
                check.get_ris(123, now - timedelta(days=1), now)

    def test_latest_available_may_be_later_than_historical_query_end(self):
        from datetime import datetime, timedelta, timezone
        end = datetime(2026, 11, 16, tzinfo=timezone.utc)
        payload = {"status": "ok", "data": {"resource": "123", "query_starttime": "2026-11-15T00:00:00",
                   "query_endtime": "2026-11-16T00:00:00", "latest_time": "2026-11-16T08:00:00",
                   "prefixes": [{"prefix": "192.0.2.0/24", "timelines": [{"starttime": "2026-11-15T00:00:00", "endtime": "2026-11-16T00:00:00"}]}]}}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return json.dumps(payload).encode()
        with patch.object(check, "urlopen", return_value=Response()):
            families, metadata = check.get_ris(123, end - timedelta(days=1), end)
        self.assertEqual(len(families[4]), 1)
        self.assertEqual(metadata["latest_time"], "2026-11-16T08:00:00")

    def test_wrong_asn_and_unrelated_timeline_are_rejected(self):
        from datetime import datetime, timedelta, timezone
        end = datetime(2026, 11, 16, tzinfo=timezone.utc)
        data = {"resource": "124", "query_starttime": "2026-11-15T00:00:00",
                "query_endtime": "2026-11-16T00:00:00", "latest_time": "2026-11-16T00:00:00",
                "prefixes": [{"prefix": "192.0.2.0/24", "timelines": [
                    {"starttime": "2026-11-13T00:00:00", "endtime": "2026-11-14T00:00:00"}]}]}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return json.dumps({"status": "ok", "data": data}).encode()
        with patch.object(check, "urlopen", return_value=Response()):
            with self.assertRaisesRegex(ValueError, "wrong ASN"):
                check.get_ris(123, end - timedelta(days=1), end)
            data["resource"] = "AS123"
            with self.assertRaisesRegex(ValueError, "timeline outside"):
                check.get_ris(123, end - timedelta(days=1), end)
