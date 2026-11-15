import base64
import contextlib
import io
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

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
        if name.endswith(".sha256sum"):
            binary = name.removesuffix(".sha256sum")
            digest = hashlib.sha256(self.blobs[binary]).hexdigest()
            data = f"{digest}  {binary}\n".encode()
        else:
            data = self.blobs[name]
        return b"stale" if url in self.stale else data

    def check(self, **opts):
        return audit.audit(REPO, SHA, audit.EDGES, self.fetch, **opts)

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

    def test_cutover_checks_release_raw_and_its_checksums(self):
        release = "c" * 40
        result = self.check(release_commit=release)
        self.assertEqual(result["release_commit"], release)
        self.assertEqual(len(self.calls), 26)
        for name in audit.FILES:
            base = f"https://raw.githubusercontent.com/{REPO}/{release}/{name}"
            self.assertIn(base, self.calls)
            self.assertIn(base + ".sha256sum", self.calls)
            rolling = f"https://github.com/{REPO}/releases/download/latest-geoip-client-v41/{name}"
            self.assertIn(rolling, self.calls)
            self.assertIn(rolling + ".sha256sum", self.calls)

    def test_consistently_stale_cdn_relative_to_release_is_rejected(self):
        release = "c" * 40
        self.stale.add(f"https://raw.githubusercontent.com/{REPO}/{release}/geoip_RU.srs")
        with self.assertRaisesRegex(ValueError, "promoted release"):
            self.check(release_commit=release)

    def test_bad_release_sidecar_is_rejected(self):
        release = "c" * 40
        self.stale.add(f"https://raw.githubusercontent.com/{REPO}/{release}/geoip_RU.dat.sha256sum")
        with self.assertRaisesRegex(ValueError, "promoted release checksum"):
            self.check(release_commit=release)

    def test_consistent_git_and_cdn_do_not_hide_stale_rolling_download(self):
        base = f"https://github.com/{REPO}/releases/download/latest-geoip-client-v41/"
        for name in ("geoip_RU.srs", "geoip_RU.srs.sha256sum"):
            with self.subTest(name=name):
                self.stale = {base + name}
                with self.assertRaisesRegex(ValueError, "rolling GitHub Release"):
                    self.check(release_commit="c" * 40)

    def test_main_rejects_a_ref_change_in_either_branch(self):
        release = "c" * 40
        for release_after, cdn_after in (("d" * 40, SHA), (release, "d" * 40)):
            with self.subTest(release=release_after, cdn=cdn_after):
                stdout, stderr = io.StringIO(), io.StringIO()
                cli = ["audit", "--repo", REPO, "--compare-release"]
                with patch.object(audit.sys, "argv", cli), \
                        patch.object(audit, "get_commit", side_effect=(SHA, release, release_after, cdn_after)), \
                        patch.object(audit, "audit", return_value={"files": {}}), \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(audit.main(), 1)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("branch moved during audit", stderr.getvalue())

    def test_inventory_matches_the_shell_publisher(self):
        shell = Path(audit.__file__).with_name("v41_cdn_files.sh").read_text()
        line = next(line for line in shell.splitlines() if "V41_CDN_FILES=" in line)
        self.assertEqual(set(line.partition("(")[2].partition(")")[0].split()), set(audit.FILES))


if __name__ == "__main__":
    unittest.main()
