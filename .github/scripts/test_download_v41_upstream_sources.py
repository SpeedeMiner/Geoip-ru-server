import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from download_v41_upstream_sources import API, fetch, resolve


class RollingSourcesTests(unittest.TestCase):
    def test_branch_is_resolved_once_for_all_related_files(self):
        repo = "Example/Publisher"
        commit, tree = "a" * 40, "b" * 40
        responses = {
            f"{API}{repo}/branches/release": {"commit": {"sha": commit, "commit": {"tree": {"sha": tree}}}},
            f"{API}{repo}/git/trees/{tree}": {"sha": tree, "tree": [
                {"path": name, "type": "blob", "mode": "100644", "size": 1, "sha": "c" * 40}
                for name in ("one", "two")]},
        }
        calls = []
        def get(url):
            calls.append(url)
            return responses[url]
        results = list(resolve({"repository": repo, "branch": "release",
                                "files": {"one": "one", "two": "two"}}, get))
        self.assertEqual(calls, list(responses))
        self.assertTrue(all(f"/{commit}/" in item[1] for item in results))

    def test_release_must_have_platform_digest_and_exact_origin(self):
        repo = "Example/Publisher"
        group = {"repository": repo, "release": "latest", "files": {"source.dat": "geoip.dat"}}
        url = f"https://github.com/{repo}/releases/download/v1/geoip.dat"
        asset = {"name": "geoip.dat", "state": "uploaded", "size": 1, "browser_download_url": url}
        meta = {"tag_name": "v1", "draft": False, "prerelease": False, "assets": [asset]}
        with self.assertRaisesRegex(ValueError, "no verifiable"):
            list(resolve(group, lambda _: meta))
        asset["digest"] = "sha256:" + "1" * 64
        self.assertEqual(list(resolve(group, lambda _: meta))[0], ("source.dat", url, 1, None, "1" * 64))
        asset["browser_download_url"] = "https://example.test/geoip.dat"
        with self.assertRaisesRegex(ValueError, "no verifiable"):
            list(resolve(group, lambda _: meta))

    def test_wrong_git_blob_rejects_without_publishing_file_or_provenance(self):
        repo = "Example/Publisher"
        commit, tree = "a" * 40, "b" * 40
        blob = hashlib.sha1(b"blob 1\0x").hexdigest()
        with TemporaryDirectory() as folder:
            root = Path(folder)
            catalog, provenance = root / "catalog.json", root / "inputs.tsv"
            catalog.write_text(json.dumps([{"repository": repo, "branch": "release",
                                            "files": {"source.dat": "geoip.dat"}}]))
            responses = {
                f"{API}{repo}/branches/release": {"commit": {"sha": commit, "commit": {"tree": {"sha": tree}}}},
                f"{API}{repo}/git/trees/{tree}": {"sha": tree, "tree": [
                    {"path": "geoip.dat", "type": "blob", "mode": "100644", "size": 1, "sha": blob}]},
            }
            def transfer(url, output, cap, *, metadata=False):
                output.write_bytes(json.dumps(responses[url]).encode() if metadata else b"y")
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                fetch(catalog, provenance, root, transfer=transfer)
            self.assertFalse(provenance.exists())
            self.assertFalse((root / "source.dat").exists())
