import base64
import hashlib
import json
from pathlib import Path
import unittest

import audit_v41_cdn_public as audit

REPO = "example/geoip"
SHA = "b" * 40


class PublicCdnAuditTests(unittest.TestCase):
    def setUp(self):
        self.blobs = {name: name.encode() + b"\0" for name in audit.FILES}
        self.calls = []
        self.rows = [
            {"name": name, "type": "file", "size": len(data),
             "hash": base64.b64encode(hashlib.sha256(data).digest()).decode()}
            for name, data in self.blobs.items()
        ]
        self.flat = [{**row, "name": "/" + row["name"]} for row in self.rows]
        self.stale = set()

    def fetch(self, url, limit):
        self.calls.append(url)
        if url.startswith("https://data.jsdelivr.com/"):
            rows = self.flat if url.endswith("/flat") else self.rows
            return json.dumps({"files": rows}).encode()
        name = url.rsplit("/", 1)[1]
        return b"stale" if url in self.stale else self.blobs[name]

    def check(self):
        return audit.audit(REPO, SHA, audit.EDGES, self.fetch)

    def test_inventory_checks_pinned_raw_and_all_requested_cdn_downloads(self):
        result = self.check()
        self.assertEqual(len(self.calls), 14)
        self.assertEqual(result["verified_hosts"], ["raw.githubusercontent.com", *audit.EDGES])
        self.assertEqual(set(result["files"]), set(audit.FILES))
        self.assertEqual(result["cdn_commit"], SHA)
        for name in audit.FILES:
            self.assertIn(f"https://raw.githubusercontent.com/{REPO}/{SHA}/{name}", self.calls)

    def test_extra_source_dat_is_rejected_even_with_right_extension(self):
        self.rows.append({**self.rows[0], "name": "hydra-geoip.dat"})
        with self.assertRaisesRegex(ValueError, "unexpected or duplicate"):
            self.check()
        self.assertEqual(len(self.calls), 1)

    def test_no_missing_duplicates_or_directory_entries(self):
        original = self.rows[:]
        for rows in (original[:-1], original + [original[0]],
                     [{**original[0], "type": "directory"}, *original[1:]]):
            with self.subTest(rows=rows):
                self.rows = rows
                with self.assertRaises(ValueError):
                    self.check()

    def test_metadata_disagreement_and_stale_edge_are_rejected(self):
        self.flat[0]["size"] += 1
        with self.assertRaisesRegex(ValueError, "inventories disagree"):
            self.check()
        self.flat[0]["size"] -= 1
        self.stale.add(f"https://gcore.jsdelivr.net/gh/{REPO}@cdn/geoip_RU.srs")
        with self.assertRaisesRegex(ValueError, "geoip_RU.srs at gcore.jsdelivr.net"):
            self.check()

    def test_same_metadata_does_not_hide_stale_pinned_origin(self):
        self.stale.add(f"https://raw.githubusercontent.com/{REPO}/{SHA}/geoip_RU.dat")
        with self.assertRaisesRegex(ValueError, "geoip_RU.dat at raw.githubusercontent.com"):
            self.check()

    def test_inventory_matches_the_shell_publisher(self):
        shell = Path(audit.__file__).with_name("v41_cdn_files.sh").read_text()
        line = next(line for line in shell.splitlines() if "V41_CDN_FILES=" in line)
        self.assertEqual(set(line.partition("(")[2].partition(")")[0].split()), set(audit.FILES))


if __name__ == "__main__":
    unittest.main()
