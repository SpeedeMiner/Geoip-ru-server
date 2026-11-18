from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from audit_v41_block_feed_delta import (
    ARCHIVE, LAYERS, LIVE_URL, MANIFEST, PINNED_APPROVED,
    PINNED_RESOLVER, PROVENANCE, RESOLVER, STATS,
    difference, format_summary, report, resolver_identity, select_live, sha, space, verify_raw,
)
from validate_v41_block_feed_counts import FALLBACK, HEADER

EMPTY = {4: [], 6: []}
NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


def record(name, resolver=b"192.0.2.1\n", *, status="LIVE_DOWNLOAD", subnet=b"203.0.113.0/24\n"):
    return {
        "release_commit": name, "status": status,
        "observed_no_later_than_utc": "2026-11-14T12:00:00+00:00",
        "fallback_resolver_sha256": "historical-feed",
        "fallback_approved_baseline_sha256": "historical-approved",
        "fallback_origin": "PINNED_V38_APPROVED_BASELINE",
        "feeds": {"antifilter-ip.lst": b"192.0.2.4\n", RESOLVER: resolver,
                  "antifilter-subnet.lst": subnet, PINNED_RESOLVER: b"192.0.2.1\n",
                  PINNED_APPROVED: b"192.0.2.1\n192.0.2.6\n"},
    }


class BlockFeedDeltaTests(unittest.TestCase):
    def test_order_duplicates_and_equivalent_split_prefixes(self):
        old = record("previous", b"192.0.2.1\n2001:db8::1\n")
        target = record("candidate", b"2001:db8::1/128\n192.0.2.1/32\n192.0.2.1\n",
                        subnet=b"203.0.113.128/25\n203.0.113.0/25\n")
        result = report(target, old, old, [], None, None, report_time=NOW)
        for name in (RESOLVER, "antifilter-subnet.lst"):
            row = result["feeds"][name]
            self.assertEqual(row["verdict"], "EQUIVALENT_ADDRESS_SPACE")
            self.assertNotEqual(row["raw_sha256"], row["baseline_raw_sha256"])
            self.assertEqual(row["address_delta"], difference(EMPTY, EMPTY))

    def test_equal_count_total_replacement_detected_in_both_families(self):
        old = record("previous", b"192.0.2.1\n2001:db8::1\n")
        target = record("candidate", b"192.0.2.2\n2001:db8::2\n")
        row = report(target, old, old, [], None, None, report_time=NOW)["feeds"][RESOLVER]
        self.assertEqual(row["verdict"], "ADDRESS_SPACE_CHANGED")
        self.assertEqual(row["address_delta"]["ipv4"]["removed"], {"addresses": "1", "cidrs": ["192.0.2.1/32"]})
        self.assertEqual(row["address_delta"]["ipv6"]["added"], {"addresses": "1", "cidrs": ["2001:db8::2/128"]})

    def test_two_fallbacks_and_recovery_use_last_live_not_pinned_v38(self):
        history = [
            record("newer-fallback", b"# placeholder\n", status="DEGRADED_V38_FALLBACK"),
            record("older-fallback", b"# placeholder\n", status="DEGRADED_V38_FALLBACK"),
            record("last-live", b"192.0.2.99\n"),
        ]
        live, visited = select_live(history)
        self.assertEqual(len(visited), 3)
        self.assertIs(live, history[2])
        target = record("candidate", b"192.0.2.100\n")
        result = report(target, history[0], live, visited, None, None, report_time=NOW)
        self.assertEqual(result["previous_release"], "newer-fallback")
        self.assertEqual(result["last_live_publication_age_seconds"], 86400)
        row = result["feeds"][RESOLVER]
        self.assertEqual(row["baseline"], "last-live")
        self.assertEqual(row["address_delta"]["ipv4"]["removed"]["cidrs"], ["192.0.2.99/32"])
        fallback = report(history[1], history[0], live, visited, None, None, report_time=NOW)["feeds"][RESOLVER]
        self.assertIsNone(fallback["address_delta"])
        self.assertEqual(fallback["verdict"], "DEGRADED_NO_LIVE_CANDIDATE")
        self.assertEqual(fallback["historical_resolver_vs_last_live"]["ipv4"]["added"]["cidrs"], ["192.0.2.1/32"])

    def test_unverified_history_is_unknown_not_a_zero_delta(self):
        rows = [{"release_commit": "gap", "status": "UNVERIFIED_RELEASE_INPUT"}]
        live, visited = select_live(rows)
        result = report(record("candidate"), None, live, visited, None, None, report_time=NOW)
        self.assertIsNone(result["last_verified_live_release"])
        self.assertIsNone(result["last_live_publication_age_seconds"])
        self.assertIsNone(result["layers_vs_previous_release"])
        self.assertEqual(result["published_history_checked"], rows)
        self.assertTrue(all(r["verdict"] == "NO_VERIFIED_BASELINE" and r["address_delta"] is None
                            for r in result["feeds"].values()))

    def test_latest_verified_live_after_gap_is_explicitly_provisional(self):
        rows = [{"release_commit": "newer", "status": "UNVERIFIED_RELEASE_INPUT"},
                record("last-live"), record("older-live")]
        live, visited = select_live(rows)
        result = report(record("candidate", b"# unavailable\n", status="DEGRADED_V38_FALLBACK"),
                        None, live, visited, None, None, report_time=NOW)
        self.assertEqual(result["last_verified_live_release"], "last-live")
        self.assertTrue(result["newer_history_gaps"])
        summary = format_summary(result)
        self.assertIn("v38 raw feed vs. last live", summary)
        self.assertIn("Newer release history contains unverified inputs", summary)

    def test_separate_layer_and_direct_intersection_delta(self):
        net = space(b"2001:db8::/32\n", strict=True)
        seed = record("previous")
        old = {**dict.fromkeys(LAYERS, net), "DIRECT": EMPTY}
        new = {**dict.fromkeys(LAYERS, net), "DIRECT": net}
        result = report(seed, seed, seed, [], new, old, report_time=NOW)["layers_vs_previous_release"]
        self.assertEqual(result["hard"]["address_space"], difference(EMPTY, EMPTY))
        added = result["hard"]["intersection_with_DIRECT"]["ipv6"]["added"]
        self.assertEqual(added, {"addresses": str(2**96), "cidrs": ["2001:db8::/32"]})

    def test_fallback_accepts_both_empty_origins_but_never_a_nonempty_download(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            feeds = record("candidate", b"# placeholder\n")["feeds"]
            status = ["antifilter-ip.lst\tAVAILABLE\t1\t1\t1\t0\t0",
                      f"{RESOLVER}\t{FALLBACK}\t0\t0\t0\t0\t0",
                      "antifilter-subnet.lst\tAVAILABLE\t1\t1\t1\t0\t0"]
            (root / STATS).write_text("\t".join(HEADER) + "\n" + "\n".join(status) + "\n")
            header = "SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"
            p = root / PROVENANCE
            p.write_text(header + f"resolver\t{RESOLVER}\t{LIVE_URL}\t-\t0\tunavailable\n")
            actual = resolver_identity(root, feeds, as_of=None)
            self.assertEqual(actual["status"], "DEGRADED_V38_FALLBACK")
            self.assertEqual(actual["fallback_approved_baseline_sha256"], sha(feeds[PINNED_APPROVED]))
            p.write_text(p.read_text().replace("unavailable", "downloaded"))
            downloaded_empty = resolver_identity(root, feeds, as_of=None)
            self.assertEqual(downloaded_empty["status"], "DEGRADED_V38_FALLBACK")
            self.assertEqual(downloaded_empty["empty_input_provenance"], "downloaded")
            with self.assertRaisesRegex(ValueError, "fallback status"):
                resolver_identity(root, {**feeds, RESOLVER: b"192.0.2.2\n"}, as_of=None)
            status[1] = f"{RESOLVER}\tAVAILABLE\t1\t1\t1\t0\t0"
            (root / STATS).write_text("\t".join(HEADER) + "\n" + "\n".join(status) + "\n")
            with self.assertRaisesRegex(ValueError, "approved_unique_hosts=0"):
                resolver_identity(root, feeds, as_of=None)

    def test_archive_digest_is_verified_before_parsing(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            from v41_release_manifest import LEGACY_SNAPSHOT
            import json
            (root / ARCHIVE).write_bytes(b"changed bytes")
            (root / PROVENANCE).write_bytes(b"unchanged")
            assets = dict.fromkeys(LEGACY_SNAPSHOT, {"bytes": 9, "sha256": sha(b"unchanged")})
            (root / MANIFEST).write_text(json.dumps({"schema": 1, "assets": assets}))
            with self.assertRaisesRegex(ValueError, "oversize asset|release asset mismatch"):
                verify_raw(root)
