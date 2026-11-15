import ipaddress
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from build_v41_overlay import load_hxehex_diagnostics, parse_ipsum
from validate_v41_block_feed_counts import FALLBACK, HEADER, REQUIRED, compare_counts, read_stats, review_digest

SCRIPT = Path(__file__).resolve().with_name("validate_v41_block_feed_counts.py")


def write_stats(path, counts):
    rows = ["\t".join(HEADER)]
    for name, (status, count) in zip(REQUIRED, counts):
        rows.append(f"{name}\t{status}\t{count}\t{count}\t{count}\t0\t0")
    path.write_text("\n".join(rows) + "\n")


class FeedQualityTests(unittest.TestCase):
    def test_exact_threshold_and_resolver_fallback(self):
        previous = dict(zip(REQUIRED, [("AVAILABLE", 100), ("AVAILABLE", 100), ("AVAILABLE", 100)]))
        candidate = dict(zip(REQUIRED, [("AVAILABLE", 50), (FALLBACK, 0), ("AVAILABLE", 151)]))
        self.assertEqual([r["verdict"] for r in compare_counts(previous, candidate)],
                         ["ok", "resolver-fallback-v38", "abrupt-count-change"])
        self.assertEqual(compare_counts(candidate, previous)[1]["verdict"], "no-usable-prior-count")

    def test_stats_reject_duplicate_missing_and_invalid_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats"
            write_stats(path, [("AVAILABLE", 10)] * 3)
            valid = path.read_text()
            for invalid in (valid + valid.splitlines()[1] + "\n",
                            "\n".join(valid.splitlines()[:-1]) + "\n",
                            valid.replace("AVAILABLE", FALLBACK, 1),
                            valid.replace("\t10\t10\t10", "\t10\t1\t10", 1)):
                path.write_text(invalid)
                with self.assertRaises(ValueError):
                    read_stats(path)

    def test_staged_publication_gate_binds_review_to_the_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = (Path(tmp) / name for name in ("old", "new"))
            write_stats(old, [("AVAILABLE", 100)] * 3)
            write_stats(new, [("AVAILABLE", 49), ("AVAILABLE", 151), ("AVAILABLE", 100)])
            feeds = [Path(tmp) / name for name in REQUIRED]
            for file in feeds:
                file.write_text(file.name)
            command = [sys.executable, str(SCRIPT), "--previous", str(old), "--candidate", str(new),
                       "--feeds", *map(str, feeds)]
            bad = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("more than 50%", bad.stderr)
            reviewed = command + ["--reviewed-sha256", review_digest(new, feeds)]
            valid = subprocess.run(reviewed, text=True, capture_output=True)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertIn("SHA-256 accepted", valid.stdout)
            feeds[0].write_text("different rows but unchanged stats")
            changed = subprocess.run(reviewed, text=True, capture_output=True)
            self.assertEqual(changed.returncode, 1)

    def test_invalid_diagnostics_do_not_confer_routing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review"
            path.write_text("<html>upstream error</html>\n")
            self.assertEqual(load_hxehex_diagnostics(path)[1]["status"], "DEGRADED_DIAGNOSTIC")
            for content in ("# optional diagnostic\n", "192.0.2.0/24\n" * 1001, "2001:db8::/32\n"):
                path.write_text(content)
                networks, stats = parse_ipsum(path)
                self.assertFalse(networks)
                self.assertEqual(stats["status"], "DEGRADED_DIAGNOSTIC")
            first = int(ipaddress.IPv4Address("192.0.0.0"))
            path.write_text("".join(f"{ipaddress.IPv4Address(first + i * 256)}/24\n" for i in range(1000)))
            networks, stats = parse_ipsum(path)
            self.assertEqual(len(networks), 1000)
            self.assertEqual(stats["status"], "AVAILABLE")

if __name__ == "__main__":
    unittest.main()
