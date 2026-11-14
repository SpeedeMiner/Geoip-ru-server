import csv
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

from verify_v41_ipverse_archive import ARCHIVE, HEADER, MIN_BYTES, archive_record, verify_archive


SCRIPTS = Path(__file__).resolve().parent
REPO = "example/geoip"
RELEASE = "a" * 40
TAG = "geoip-v41-snapshot-123.1"
URL = "https://codeload.github.com/ipverse/as-ip-blocks/tar.gz/refs/heads/master"


class IpverseArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = gzip.compress(random.Random(41).randbytes(MIN_BYTES), compresslevel=1, mtime=0)
        cls.digest = sha256(cls.raw).hexdigest()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.provenance = self.root / "provenance.tsv"
        self.payload = self.root / ARCHIVE
        self.payload.write_bytes(self.raw)
        self.out = self.root / "received.tar.gz"
        self.marker = self.root / "marker"
        self.marker.write_text(TAG + "\n")
        self.log = self.root / "requests"
        self.write_provenance()
        curl = self.root / "curl"
        curl.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "url=sys.argv[-1]\n"
            "with open(os.environ['REQUEST_LOG'], 'a') as f: f.write(json.dumps(url)+'\\n')\n"
            "out=pathlib.Path(sys.argv[sys.argv.index('--output')+1])\n"
            "if url.startswith('https://raw.githubusercontent.com/'):\n"
            "    out.write_bytes(pathlib.Path(os.environ['MARKER']).read_bytes())\n"
            "    print(os.environ.get('MARKER_STATUS','200'), end='')\n"
            "elif os.environ.get('PAYLOAD_ERROR'):\n"
            "    sys.exit(22)\n"
            "else:\n"
            "    out.write_bytes(pathlib.Path(os.environ['PAYLOAD']).read_bytes())\n"
        )
        curl.chmod(0o700)

    def write_provenance(self, **updates):
        row = dict(zip(HEADER, ("IPVERSE ASN/BGP ARCHIVE", ARCHIVE, URL,
                               self.digest, str(len(self.raw)), "downloaded")))
        row.update(updates)
        with self.provenance.open("w", newline="") as stream:
            w = csv.DictWriter(stream, HEADER, delimiter="\t", lineterminator="\n")
            w.writeheader()
            w.writerow(row)

    def retrieve(self, **env):
        return subprocess.run(
            ["bash", str(SCRIPTS / "fetch_v41_audit_ipverse.sh"), REPO, RELEASE,
             str(self.provenance), str(self.out)],
            text=True, capture_output=True, timeout=10,
            env={**os.environ, "PATH": f"{self.root}:{os.environ['PATH']}",
                 "REQUEST_LOG": str(self.log), "MARKER": str(self.marker),
                 "PAYLOAD": str(self.payload), **env},
        )

    def requests(self):
        return [json.loads(x) for x in self.log.read_text().splitlines()]

    def test_exact_archive_and_same_size_corruption(self):
        self.assertEqual(archive_record(self.provenance), (URL, self.digest, len(self.raw)))
        verify_archive(self.provenance, self.payload)
        self.payload.write_bytes(self.raw[:-1] + bytes([self.raw[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            verify_archive(self.provenance, self.payload)

    def test_rejects_bad_bounds_url_and_duplicate_rows(self):
        for change in ({"BYTES": "4999999"}, {"BYTES": "67108865"},
                       {"FETCH_URL": "http://example.test/archive"},
                       {"FETCH_URL": "https://user@example.test/archive"},
                       {"STATUS": "unavailable"}):
            with self.subTest(change=change):
                self.write_provenance(**change)
                with self.assertRaises(ValueError):
                    archive_record(self.provenance)
        self.write_provenance()
        data = self.provenance.read_text()
        self.provenance.write_text(data + data.splitlines()[1] + "\n")
        with self.assertRaisesRegex(ValueError, "one complete"):
            archive_record(self.provenance)

    def test_retained_asset_is_pinned_to_selected_release_and_checks_bytes(self):
        result = self.retrieve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.out.read_bytes(), self.raw)
        self.assertEqual(self.requests(), [
            f"https://raw.githubusercontent.com/{REPO}/{RELEASE}/geoip_RU_ipverse_snapshot_tag.txt",
            f"https://github.com/{REPO}/releases/download/{TAG}/{ARCHIVE}",
        ])

    def test_legacy_404_falls_back_but_rejects_upstream_drift(self):
        result = self.retrieve(MARKER_STATUS="404")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests()[-1], URL)
        self.payload.write_bytes(self.raw[:-1])
        failed = self.retrieve(MARKER_STATUS="404")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("size mismatch", failed.stderr)
        self.assertEqual(self.out.read_bytes(), self.raw)

    def test_missing_retained_asset_never_falls_back_to_mutable_url(self):
        result = self.retrieve(PAYLOAD_ERROR="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.out.exists())
        self.assertEqual(len(self.requests()), 2)
        self.assertNotIn(URL, self.requests())

    def test_malformed_marker_and_transport_error_do_not_trigger_fallback(self):
        self.marker.write_text("latest-geoip-client-v41\n")
        bad = self.retrieve()
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("invalid snapshot archive tag", bad.stderr)
        self.assertEqual(len(self.requests()), 1)
        forbidden = self.retrieve(MARKER_STATUS="403")
        self.assertNotEqual(forbidden.returncode, 0)
        self.assertEqual(len(self.requests()), 2)
        self.assertNotIn(URL, self.requests())
