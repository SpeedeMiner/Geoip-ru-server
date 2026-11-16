import ipaddress
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from build_v41_overlay import encode_geoip
import validate_v41_publication_review as gate

SCRIPTS = Path(__file__).resolve().parent
TABLE = SCRIPTS.parent / "data/v41-publication-review-prefixes.tsv"


class ScopedPublicationReviewTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.old = self.make_dat("old", "177.29.253.0/24")

    def make_dat(self, name, *prefixes):
        path = self.root / name
        path.write_bytes(encode_geoip({
            "RU": {ipaddress.ip_network(p) for p in (*prefixes, "198.18.0.0/24", "2001:db8:1::/48")},
            "PRIVATE": {ipaddress.ip_network("10.0.0.0/8")},
        }))
        return path

    def inspect(self, *new):
        return gate.inspect(self.make_dat("new", *new), self.old, TABLE)

    def test_unchanged_and_unrelated_changes_pass(self):
        self.assertEqual(gate.inspect(self.old, self.old, TABLE)["status"], "PASS")
        self.assertEqual(self.inspect("177.29.253.0/24", "48.103.231.0/24")["status"], "PASS")

    def test_directions_are_independent(self):
        self.old = self.make_dat("old", "48.103.230.0/24")
        result = self.inspect("177.29.253.0/24")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["watched_changes"], [])

    def test_larger_cidr_clips_to_watched_prefix(self):
        self.old = self.make_dat("old", "177.29.252.0/23")
        result = self.inspect("177.29.252.0/24", "48.103.230.0/23")
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["watched_addresses"], {"added": 256, "removed": 256})
        self.assertEqual([row["cidrs"] for row in result["watched_changes"]],
                         [["48.103.230.0/24"], ["177.29.253.0/24"]])

    def test_partial_changes_and_equal_size_substitution(self):
        self.old = self.make_dat("old", "177.29.253.0/25", "48.103.230.0/25")
        result = self.inspect("177.29.253.128/25", "48.103.230.128/25")
        self.assertEqual(result["watched_addresses"], {"added": 128, "removed": 128})
        self.assertEqual([row["cidrs"] for row in result["watched_changes"]],
                         [["48.103.230.128/25"], ["177.29.253.0/25"]])

    def test_already_present_in_both_is_not_a_delta(self):
        self.old = self.make_dat("old", "48.103.230.0/24")
        self.assertEqual(self.inspect("48.103.230.0/24")["status"], "PASS")

    def test_interval_math_matches_host_set_oracle(self):
        rng = random.Random(523)
        for _ in range(250):
            model = [set(rng.sample(range(512), rng.randint(0, 512))) for _ in range(2)]
            intervals = []
            for sample in model:
                rows = []
                for addr in sorted(sample):
                    if rows and rows[-1][1] == addr - 1:
                        rows[-1] = (rows[-1][0], addr)
                    else:
                        rows.append((addr, addr))
                intervals.append(gate.clip(rows, 128, 383))
            actual = {addr for a, z in gate.subtract(*intervals) for addr in range(a, z + 1)}
            self.assertEqual(actual, (model[0] - model[1]) & set(range(128, 384)))

    def test_invalid_review_table_fails_closed(self):
        variants = (
            "", gate.HEADER + "\n", gate.HEADER + "\nignore\t48.103.230.0/24\treason\n",
            gate.HEADER + "\nadded\t48.103.230.1/24\treason\n",
            gate.HEADER + "\nadded\t48.103.230.0/23\treason\n",
            gate.HEADER + "\nadded\t2001:db8::/32\treason\n",
            gate.HEADER + "\nadded\t48.103.230.0/24\t\n",
            gate.HEADER + "\n" + "added\t48.103.230.0/24\treason\n" * 2,
            gate.HEADER + "\n" + "x" * (gate.MAX_TABLE_BYTES + 1),
        )
        p = self.root / "rules.tsv"
        for content in variants:
            with self.subTest(content=content[:100]):
                p.write_text(content)
                with self.assertRaises(ValueError):
                    gate.inspect(self.old, self.old, p)

    def test_cli_hold_exit_and_json_not_bypassed_by_size_review_override(self):
        candidate = self.make_dat("new")
        result = subprocess.run([
            sys.executable, str(SCRIPTS / "validate_v41_publication_review.py"),
            "--candidate", str(candidate), "--reference", str(self.old), "--table", str(TABLE),
        ], env={**os.environ, "REVIEWED_SHA": gate.sha256(candidate.read_bytes()).hexdigest()},
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        doc = json.loads(result.stdout)
        self.assertEqual(doc["status"], "HOLD")
        self.assertEqual(doc["watched_addresses"], {"added": 0, "removed": 256})
        self.assertIn("Scoped DIRECT publication review required", result.stderr)

    def test_malformed_dat_is_not_a_pass(self):
        path = self.root / "invalid.dat"
        path.write_bytes(b"invalid")
        with self.assertRaises(ValueError):
            gate.inspect(path, self.old, TABLE)


if __name__ == "__main__":
    unittest.main()
