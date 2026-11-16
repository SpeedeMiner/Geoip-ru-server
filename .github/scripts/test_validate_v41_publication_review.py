import ipaddress
import json
import os
from pathlib import Path
import random
import shutil
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

    def test_shell_preflight_controls_first_write(self):
        # Hermetic shell integration: stub unrelated gates and remote reads,
        # but execute the actual checksum, bounds, scoped guard and pipefail.
        root = self.root
        for sub in (".github/scripts", ".github/data", "candidate", "temp", "bin"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        for name in ("verify_v41_publication_candidate.sh", "validate_v41_publication_bounds.py",
                     "validate_v41_publication_review.py"):
            shutil.copyfile(SCRIPTS / name, root / ".github/scripts" / name)
        shutil.copyfile(TABLE, root / ".github/data" / TABLE.name)
        (root / "old.sha").write_text(gate.sha256(self.old.read_bytes()).hexdigest() + "\n")
        (root / "stub").write_text("stub\n")
        bin_dir = root / "bin"
        stubs = {
            "git": '#!/bin/bash\nprintf "%040d\\trefs/heads/release\\n" 1\n',
            "curl": (
                '#!/bin/bash\nfor last do :; done\n'
                'case "$last" in\n'
                '  */previous-geoip.dat) cp "$TEST_ROOT/old" "$last";;\n'
                '  */previous-geoip.sha) cp "$TEST_ROOT/old.sha" "$last";;\n'
                '  *) cp "$TEST_ROOT/stub" "$last";;\n'
                'esac\n'),
            "python3": (
                '#!/bin/bash\ncase "$1" in\n'
                '  */validate_v41_publication_bounds.py|*/validate_v41_publication_review.py)'
                ' exec "$TEST_PYTHON" "$@";;\n'
                '  *) exit 0;;\n'
                'esac\n'),
        }
        for name, content in stubs.items():
            path = bin_dir / name
            path.write_text(content)
            path.chmod(0o700)
        cwd = root / "candidate"
        (cwd / "quality").write_text("PRE_PUBLICATION_V41_HARD_POLICY_GATE\n")
        for name in ("output", "geoip_RU.srs", "geoip_PRIVATE.srs", "mask", "block", "rir", "upstream"):
            (cwd / name).write_text(name)
            (cwd / (name + ".sha256sum")).write_text(
                f"{gate.sha256((cwd / name).read_bytes()).hexdigest()}  {name}\n")
        env = {
            **os.environ, "TEST_ROOT": str(root), "TEST_PYTHON": sys.executable,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "RUNNER_TEMP": str(root / "temp"), "GITHUB_REPOSITORY": "example/fixture",
            "GITHUB_STEP_SUMMARY": str(root / "summary"), "GITHUB_ENV": str(root / "env"),
            "OUTPUT_SHA_FILE": "output.sha256sum", "V41_BLOCKED_SHA": "mask.sha256sum",
            "BLOCK_INPUTS_SHA": "block.sha256sum", "REGISTRY_INPUTS_SHA": "rir.sha256sum",
            "UPSTREAM_INPUTS_SHA": "upstream.sha256sum", "INPUT_PROVENANCE": "provenance",
            "BLOCK_INPUTS_ARCHIVE": "block", "RELEASE_MANIFEST": "manifest",
            "REGISTRY_INPUTS_ARCHIVE": "rir", "UPSTREAM_INPUTS_ARCHIVE": "upstream",
            "IPVERSE_BGP_ARCHIVE": "ipverse", "V41_OUTPUT_FILE": "candidate.dat",
            "TELEGRAM_OFFICIAL_INPUT": "telegram", "V41_QUALITY_REPORT": "quality",
            "BLOCKED_STATS_INPUT": "stats", "BLOCKED_IP_RAW_INPUT": "ip",
            "BLOCKED_IPRESOLVE_INPUT": "ipresolve", "BLOCKED_SUBNET_INPUT": "subnet",
        }
        for hold, table_missing in ((False, False), (True, False), (False, True)):
            with self.subTest(hold=hold, table_missing=table_missing):
                for n in ("summary", "env", "first-write"):
                    (root / n).unlink(missing_ok=True)
                if table_missing:
                    (root / ".github/data" / TABLE.name).unlink()
                candidate = self.make_dat("new", "48.103.230.0/24") if hold else self.old
                shutil.copyfile(candidate, cwd / "candidate.dat")
                digest = gate.sha256(candidate.read_bytes()).hexdigest()
                result = subprocess.run(
                    ["bash", "-c", 'bash ../.github/scripts/verify_v41_publication_candidate.sh '
                     '&& touch "$TEST_ROOT/first-write"'],
                    cwd=cwd, env={**env, "REVIEWED_SHA": digest}, capture_output=True, text=True, check=False)
                blocked = hold or table_missing
                self.assertEqual(result.returncode, int(blocked), result.stderr)
                self.assertEqual((root / "first-write").exists(), not blocked)
                self.assertEqual((root / "env").exists(), not blocked)
                if not table_missing:
                    summary = json.loads((root / "summary").read_text().splitlines()[-1])
                    self.assertEqual(summary["status"], "HOLD" if hold else "PASS")
                else:
                    self.assertIn("Cannot evaluate scoped publication review", result.stderr)


if __name__ == "__main__":
    unittest.main()
