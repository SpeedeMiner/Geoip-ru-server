import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from bundle_v41_registry_inputs import create, restore
from download_v41_upstream_sources import API, TransferError, fetch
from v41_diagnostic_sources import HXEHEX_FILES, HXEHEX_REPO, IPSUM, IPSUM_LABEL, IPSUM_URL, STATUS
from v41_diagnostic_sources import placeholder, unavailable_metadata
from validate_v41_block_feed_counts import compare_content, read_feed_hashes

HEADER = "SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"


class DiagnosticTransportTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.provenance = self.root / "inputs.tsv"
        self.provenance.write_text(HEADER)
        self.catalog = self.root / "catalog.json"
        self.catalog.write_text(json.dumps([{"repository": HXEHEX_REPO, "branch": "main",
                                             "files": HXEHEX_FILES}]))
        self.commit, self.tree = "a" * 40, "b" * 40
        self.branch = f"{API}{HXEHEX_REPO}/branches/main"
        self.tree_url = f"{API}{HXEHEX_REPO}/git/trees/{self.tree}"
        self.responses = {
            self.branch: {"commit": {"sha": self.commit, "commit": {"tree": {"sha": self.tree}}}},
            self.tree_url: {"sha": self.tree, "tree": [
                {"path": path, "type": "blob", "mode": "100644", "size": 1,
                 "sha": hashlib.sha1(b"blob 1\0x").hexdigest()} for path in HXEHEX_FILES.values()]},
        }

    def test_metadata_outage_archives_replayable_diagnostic_placeholders(self):
        def unavailable(url, output, cap, **kwargs):
            raise TransferError(url)
        fetch(self.catalog, self.provenance, self.root, transfer=unavailable)
        self.assertEqual(self.provenance.read_text().count(STATUS), 2)
        archive = self.root / "bundle.tar.gz"
        dest = self.root / "restored"
        create(self.provenance, self.root, archive, members=tuple(HXEHEX_FILES))
        restore(self.provenance, archive, dest, members=tuple(HXEHEX_FILES))
        for name in HXEHEX_FILES:
            self.assertEqual((dest / name).read_bytes(), placeholder(self.branch))
        (self.root / next(iter(HXEHEX_FILES))).write_bytes(b"unexpected data")
        with self.assertRaises(ValueError):
            create(self.provenance, self.root, self.root / "bad.tar.gz", members=tuple(HXEHEX_FILES))

    def test_one_blob_outage_preserves_other_verified_blob(self):
        def transfer(url, output, cap, *, metadata=False):
            if url.endswith("/ipwhitelist.txt"):
                output.write_bytes(b"partial transfer")
                raise TransferError(url)
            output.write_bytes(json.dumps(self.responses[url]).encode() if metadata else b"x")
        fetch(self.catalog, self.provenance, self.root, transfer=transfer)
        self.assertEqual((self.root / "hxehex-cidrwhitelist.txt").read_bytes(), b"x")
        expected = f"https://raw.githubusercontent.com/{HXEHEX_REPO}/{self.commit}/ipwhitelist.txt"
        self.assertEqual((self.root / "hxehex-ipwhitelist.txt").read_bytes(), placeholder(expected))
        self.assertEqual(self.provenance.read_text().count(STATUS), 1)

    def test_identity_error_in_optional_input_is_still_fatal(self):
        def transfer(url, output, cap, *, metadata=False):
            output.write_bytes(json.dumps(self.responses[url]).encode() if metadata else b"y")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            fetch(self.catalog, self.provenance, self.root, transfer=transfer)
        self.assertEqual(self.provenance.read_text(), HEADER)

    def test_unavailability_cannot_extend_to_routing_source(self):
        self.catalog.write_text(json.dumps([{"repository": HXEHEX_REPO, "branch": "main",
                                             "files": {**HXEHEX_FILES, "other.dat": "geoip.dat"}}]))
        def unavailable(url, output, cap, **kwargs):
            raise TransferError(url)
        with self.assertRaises(TransferError):
            fetch(self.catalog, self.provenance, self.root, transfer=unavailable)
        self.assertEqual(self.provenance.read_text(), HEADER)
        for name in ("antifilter-subnet.lst", "w1zardz-ru-ipv4.txt", "hxehex-ipwhitelist.txt"):
            with self.assertRaisesRegex(ValueError, "unexpected unavailable"):
                unavailable_metadata(name, IPSUM_LABEL, IPSUM_URL, "-", "0")

    def test_ipsum_shell_fallback_consumes_same_placeholder_as_archive(self):
        # Exercise the actual shell downloader with a failed curl and a partial result.
        shell = (Path(__file__).parent / "download_v41_build_inputs.sh").read_text()
        helpers = shell[shell.index("record_source_download()"):shell.index("# Resolve each publisher")]
        start = shell.index(f'download_optional_file "{IPSUM_LABEL}"')
        call = shell[start:shell.index("\n\n", start)]
        subprocess.run(["bash", "-euo", "pipefail", "-c",
                        helpers + '\ncurl() { printf partial > "${@: -2:1}"; return 22; }\n' + call],
                       cwd=self.root, check=True, capture_output=True,
                       env={**os.environ, "INPUT_PROVENANCE": str(self.provenance), "BLOCKED_IPSUM_INPUT": IPSUM})
        source, name, url, digest, size, status = self.provenance.read_text().splitlines()[1].split("\t")
        self.assertEqual(status, STATUS)
        self.assertEqual(unavailable_metadata(name, source, url, digest, size), placeholder(IPSUM_URL))
        create(self.provenance, self.root, self.root / "ipsum.tar.gz", members=(IPSUM,))


class ContentObservationTests(unittest.TestCase):
    def test_equal_count_does_not_mean_equal_content_and_fallback_is_not_baseline(self):
        ip, resolved, subnet = ("antifilter-ip.lst", "antifilter-ipresolve.lst", "antifilter-subnet.lst")
        a, b = "a" * 64, "b" * 64
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.tsv"
            path.write_text(HEADER + f"A\t{ip}\thttps://example.test/ip\t{a}\t20\tdownloaded\n"
                            + f"B\t{resolved}\thttps://example.test/r\t-\t0\tunavailable\n"
                            + f"C\t{subnet}\thttps://example.test/sub\t{a}\t30\tdownloaded\n")
            old = read_feed_hashes(path)
        results = list(compare_content(old, {ip: b, resolved: a, subnet: a}, [
            {"source": ip, "verdict": "ok"}, {"source": resolved, "verdict": "no-usable-prior-count"},
            {"source": subnet, "verdict": "ok"},
        ]))
        self.assertEqual([r["content"] for r in results], [
            "changed-since-previous-release", "no-live-baseline", "unchanged-since-previous-release",
        ])
