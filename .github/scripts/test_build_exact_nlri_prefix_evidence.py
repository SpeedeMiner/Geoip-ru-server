from __future__ import annotations

import unittest
from collect_exact_nlri_live_evidence import build_plan, summarize


class ExactNlriCaptureTests(unittest.TestCase):
    def test_plan_covers_exact_prefixes_and_each_source_once(self):
        plan = build_plan()
        self.assertEqual(len(plan), 20)
        self.assertEqual(
            {row["prefix"] for row in plan},
            {
                "93.181.240.0/20", "93.181.248.0/21",
                "94.131.190.0/23", "94.131.190.0/24", "94.131.191.0/24",
            },
        )
        self.assertEqual(
            {source: sum(row["source"] == source for row in plan)
             for source in {row["source"] for row in plan}},
            {
                "routeviews_exact_rib": 5,
                "routeviews_timestamped_rpki": 5,
                "ripestat_routing_status": 5,
                "ripestat_looking_glass_24h": 5,
            },
        )
        self.assertTrue(all(row["url"].startswith("https://") for row in plan))

    def test_routeviews_exact_summary_keeps_peer_and_origin_observations(self):
        record = {
            "prefix": "93.181.240.0/20",
            "source": "routeviews_exact_rib",
            "transport_status": "HTTP_OK",
            "http_status": 200,
            "response_received_utc": "2026-11-11T10:00:00Z",
            "response_json": [
                {
                    "prefix": "93.181.240.0/20",
                    "origin_asn": 13118,
                    "rpki_state": "valid",
                    "reporting_peers": [
                        {"peer_asn": 123, "timestamp": "2026-11-11T09:58:00Z"},
                        {"peer_asn": 456, "timestamp": "2026-11-11T09:59:00Z"},
                    ],
                },
                {
                    "prefix": "93.181.248.0/21",
                    "origin_asn": 12389,
                    "rpki_state": "valid",
                    "reporting_peers": [{"timestamp": "2026-11-11T09:59:00Z"}],
                },
            ],
        }
        summary = summarize(record)
        self.assertEqual(summary["exact_entries_returned"], 1)
        self.assertEqual(summary["origins"], ["13118"])
        self.assertEqual(summary["rpki_states"], ["valid"])
        self.assertEqual(summary["reporting_peer_count"], 2)
        self.assertEqual(summary["latest_peer_timestamp"], "2026-11-11T09:59:00Z")

    def test_routeviews_rpki_summary_preserves_snapshot_timestamp_and_per_asn_status(self):
        record = {
            "prefix": "94.131.190.0/23",
            "source": "routeviews_timestamped_rpki",
            "transport_status": "HTTP_OK",
            "http_status": 200,
            "response_received_utc": "2026-11-11T10:00:00Z",
            "response_json": {
                "94.131.190.0/23": {
                    "timestamp": "2026-11-11T08:00:00+00:00",
                    "asn": [{"215013": "invalid"}, {"219109": "notfound"}],
                }
            },
        }
        summary = summarize(record)
        self.assertTrue(summary["prefix_key_present"])
        self.assertEqual(summary["snapshot_timestamp"], "2026-11-11T08:00:00+00:00")
        self.assertEqual(summary["origin_states"], {"215013": "invalid", "219109": "notfound"})

    def test_routeviews_rpki_preserves_null_exact_prefix_result(self):
        record = {
            "prefix": "94.131.190.0/23",
            "source": "routeviews_timestamped_rpki",
            "transport_status": "HTTP_OK",
            "http_status": 200,
            "response_received_utc": "2026-11-11T10:00:00Z",
            "response_json": {"94.131.190.0/23": None},
        }
        summary = summarize(record)
        self.assertTrue(summary["prefix_key_present"])
        self.assertTrue(summary["prefix_entry_is_null"])
        self.assertIsNone(summary["snapshot_timestamp"])
        self.assertEqual(summary["origin_states"], {})

    def test_ripestat_routing_status_summary_keeps_exact_origin_scope(self):
        record = {
            "prefix": "94.131.190.0/23",
            "source": "ripestat_routing_status",
            "transport_status": "HTTP_OK",
            "http_status": 200,
            "response_received_utc": "2026-11-11T10:00:00Z",
            "response_json": {
                "status": "ok",
                "data": {
                    "query_time": "2026-11-11T08:00:00",
                    "origins": [{"origin": 215013, "route_objects": ["RIPE"]}],
                    "less_specifics": [],
                    "more_specifics": [{"prefix": "94.131.190.0/24", "origin": 215013}],
                },
            },
        }
        summary = summarize(record)
        self.assertEqual(summary["api_status"], "ok")
        self.assertEqual(summary["exact_origins"], [{"origin": 215013, "route_objects": ["RIPE"]}])
        self.assertEqual(summary["more_specific_count"], 1)

    def test_ripestat_looking_glass_parses_rrc_peer_arrays(self):
        record = {
            "prefix": "94.131.190.0/24",
            "source": "ripestat_looking_glass_24h",
            "transport_status": "HTTP_OK",
            "http_status": 200,
            "response_received_utc": "2026-11-11T10:00:00Z",
            "response_json": {
                "status": "ok",
                "data": {
                    "query_time": "2026-11-11T09:59:00",
                    "latest_time": "2026-11-11T09:58:00",
                    "rrcs": [
                        {
                            "rrc": "rrc00",
                            "location": "Amsterdam",
                            "peers": [
                                {
                                    "asn_origin": "215013",
                                    "prefix": "94.131.190.0/24",
                                    "peer": "192.0.2.1",
                                    "as_path": "64500 215013",
                                    "last_updated": "2026-11-10T20:00:00",
                                    "latest_time": "2026-11-11T09:58:00",
                                },
                                {
                                    "asn_origin": "219109",
                                    "prefix": "94.131.190.0/24",
                                    "peer": "192.0.2.2",
                                    "as_path": "64501 219109",
                                    "last_updated": "2026-11-10T20:01:00",
                                    "latest_time": "2026-11-11T09:57:00",
                                },
                            ],
                        }
                    ],
                },
            },
        }
        summary = summarize(record)
        self.assertEqual(summary["api_status"], "ok")
        self.assertEqual(summary["rrc_count"], 1)
        self.assertEqual(summary["peer_observation_count"], 2)
        self.assertEqual(summary["origins"], ["215013", "219109"])
        self.assertEqual(summary["latest_time"], "2026-11-11T09:58:00")
        self.assertEqual(summary["peer_observations"][0]["rrc"], "rrc00")

    def test_transport_error_is_preserved_not_interpreted_as_absence(self):
        record = {
            "prefix": "94.131.190.0/23",
            "source": "routeviews_exact_rib",
            "transport_status": "NETWORK_ERROR",
            "http_status": None,
            "response_received_utc": "2026-11-11T10:00:00Z",
            "error": "URLError: DNS failure",
            "response_json": None,
        }
        summary = summarize(record)
        self.assertEqual(summary["transport_status"], "NETWORK_ERROR")
        self.assertEqual(summary["error"], "URLError: DNS failure")
        self.assertNotIn("exact_entries_returned", summary)


if __name__ == "__main__":
    unittest.main()
