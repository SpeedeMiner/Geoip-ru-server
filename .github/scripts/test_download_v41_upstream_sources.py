import hashlib
import ipaddress
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from download_v41_upstream_sources import API, TEXT_PREFIX_FEEDS, fetch, resolve, validate_text_prefix_feed


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

    def test_required_text_lists_count_distinct_cidrs_per_expected_family(self):
        for name, (family, floor) in TEXT_PREFIX_FEEDS.items():
            sample = ipaddress.ip_address("2001:db8::" if family == 6 else "198.18.0.0")
            rows = [f"{sample + offset}/{sample.max_prefixlen}" for offset in range(floor)]
            with self.subTest(name=name):
                valid = ("# fixture\n" + "\n".join(rows) + " # allowed comment\n").encode("utf-8-sig")
                self.assertEqual(validate_text_prefix_feed(name, valid), (0, floor) if family == 6 else (floor, 0))
                padded = ("\n".join(rows[:-1] + ([rows[0]] * 10)) + "\n").encode()
                with self.assertRaisesRegex(ValueError, f"only {floor - 1} distinct"):
                    validate_text_prefix_feed(name, padded)

    def test_required_text_lists_reject_ambiguous_and_invalid_tokens(self):
        examples = (
            b"not a route", b'{"error":"truncated"}', b"192.0.2.1", b"192.0.2.1/24",
            b"0.0.0.0/0", b"::/0", b"fe80::%eth0/64", b"192.0.2.0/255.255.255.0",
            b"192.0.2.0/24 198.51.100.0/24", b"IP-CIDR,192.0.2.0/24", bytes([255]),
        )
        for entry in examples:
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, "expected"):
                validate_text_prefix_feed("escapingworm-operator-cidr.txt", b"198.51.100.0/24\n" + entry)
        with self.assertRaisesRegex(ValueError, "expected an aligned non-default IPv4 CIDR"):
            validate_text_prefix_feed("kyoresuas-ru-standard-ipv4.txt", b"2001:db8::/48")
        with self.assertRaisesRegex(ValueError, "expected an aligned non-default IPv6 CIDR"):
            validate_text_prefix_feed("kyoresuas-ru-standard-ipv6.txt", b"198.51.100.0/24")

    def test_matching_git_hash_does_not_adopt_invalid_required_text_or_staged_files(self):
        repo = "Example/Publisher"
        commit, tree = "a" * 40, "b" * 40
        required = "w1zardz-ru-ipv4.txt"
        blobs = {"one.dat": b"nonempty valid identity", required: b'{"error":"upstream broken"}'}
        with TemporaryDirectory() as folder:
            root = Path(folder)
            catalog, provenance = root / "catalog.json", root / "inputs.tsv"
            catalog.write_text(json.dumps([{"repository": repo, "branch": "release",
                                            "files": {name: name for name in blobs}}]))
            provenance.write_bytes(b"prior provenance\n")
            (root / "one.dat").write_bytes(b"prior bytes")
            responses = {
                f"{API}{repo}/branches/release": {"commit": {"sha": commit, "commit": {"tree": {"sha": tree}}}},
                f"{API}{repo}/git/trees/{tree}": {"sha": tree, "tree": [
                    {"path": name, "type": "blob", "mode": "100644", "size": len(data),
                     "sha": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()}
                    for name, data in blobs.items()]},
            }

            def transfer(url, output, cap, *, metadata=False):
                output.write_bytes(json.dumps(responses[url]).encode() if metadata else blobs[url.rsplit("/", 1)[1]])

            with self.assertRaisesRegex(ValueError, "expected an aligned non-default IPv4 CIDR"):
                fetch(catalog, provenance, root, transfer=transfer)
            self.assertEqual(provenance.read_bytes(), b"prior provenance\n")
            self.assertEqual((root / "one.dat").read_bytes(), b"prior bytes")
            self.assertFalse((root / required).exists())
