from pathlib import Path
import json
from tempfile import TemporaryDirectory
import unittest

import validate_v41_source_health as health


class SourceHealthTests(unittest.TestCase):
    def test_catalog_required_files_are_not_silently_omitted(self):
        path = Path(__file__).resolve().parent.parent / "data/v41-upstream-sources.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        names = {name for group in catalog for name in group["files"]}
        diagnostic = {"hxehex-cidrwhitelist.txt", "hxehex-ipwhitelist.txt"}
        self.assertLessEqual(names - diagnostic, health.REQUIRED)

    def write(self, path, *, omit=None, bad=None):
        rows = ["SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"]
        for name in sorted(health.REQUIRED - ({omit} if omit else set())):
            rows.append(f"test\t{name}\thttps://example.test/x\t{'a' * 64}\t1000\t{'unavailable' if name == bad else 'downloaded'}\n")
        path.write_text("".join(rows), encoding="utf-8")

    def test_requires_each_source_and_downloaded_status(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "inputs.tsv"
            self.write(path)
            baseline = health.read_provenance(path)
            self.assertEqual(len(baseline), len(health.REQUIRED))
            name = sorted(health.REQUIRED)[0]
            self.write(path, omit=name)
            with self.assertRaisesRegex(ValueError, "missing required"):
                health.read_provenance(path)
            self.write(path, bad=name)
            with self.assertRaisesRegex(ValueError, "invalid or duplicate"):
                health.read_provenance(path)

    def test_below_half_is_flagged_without_confusing_exact_half(self):
        old = dict.fromkeys(health.REQUIRED, 1000)
        current = dict(old)
        names = sorted(health.REQUIRED)
        current[names[0]] = 499
        current[names[1]] = 500
        rows = {row["file"]: row for row in health.compare(old, current)}
        self.assertTrue(rows[names[0]]["needs_review"])
        self.assertFalse(rows[names[1]]["needs_review"])
        with self.assertRaisesRegex(ValueError, "fell below 50%"):
            health.enforce(list(rows.values()))
        health.enforce(list(rows.values()), report_only=True)
