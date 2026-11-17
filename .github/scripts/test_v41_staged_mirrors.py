import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
from tempfile import TemporaryDirectory
import unittest


from verify_v41_ipverse_archive import validate_ipverse


SCRIPTS = Path(__file__).resolve().parent
REF = "2026-09-01"
PRIMARY = "https://first.test/feed"
MIRROR = "https://second.test/feed"


class DownloadMirrorTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / ".github").mkdir()
        (self.root / ".github/scripts").symlink_to(SCRIPTS, target_is_directory=True)
        self.provenance = self.root / "provenance.tsv"
        self.provenance.touch()
        self.output = self.root / "source"
        self.output.write_bytes(b"previous run")
        script = (SCRIPTS / "download_v41_build_inputs.sh").read_text()
        self.helpers = script[script.index("record_source_download()"):script.index("# Pin one UTC date")]

    def download(self, first, second):
        for name, blob in (("first", first), ("second", second)):
            (self.root / name).write_bytes(blob)
        mock = """
curl() {
  case "${@: -1}" in
    https://first.test/feed) cp first "${@: -2:1}" ;;
    https://second.test/feed) cp second "${@: -2:1}" ;;
    *) return 22 ;;
  esac
}
"""
        return subprocess.run(
            ["bash", "-euo", "pipefail", "-c", self.helpers + mock + '\ndownload_file "$@"',
             "_", "TELEGRAM OFFICIAL CIDRS", self.output.name, PRIMARY, MIRROR],
            cwd=self.root, text=True, capture_output=True,
            env={**os.environ, "INPUT_PROVENANCE": str(self.provenance), "rir_reference_utc": REF},
        )

    def test_http_success_with_html_tries_next_mirror_and_records_only_valid_url(self):
        valid = (SCRIPTS.parent / "data/v41-telegram-official-cidrs.txt").read_bytes()
        run = self.download(b"<!doctype html><html>Upstream unavailable</html>", valid)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.output.read_bytes(), valid)
        self.assertEqual(self.provenance.read_text().splitlines(), [
            f"TELEGRAM OFFICIAL CIDRS\tsource\t{MIRROR}\t{hashlib.sha256(valid).hexdigest()}\t{len(valid)}\tdownloaded"
        ])
        self.assertFalse((self.root / "source.part").exists())

    def test_required_all_invalid_fails_even_if_old_output_exists(self):
        run = self.download(b"<html>", b"")
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertEqual(self.provenance.read_text(), "")
        self.assertEqual(self.output.read_bytes(), b"previous run")
        self.assertFalse((self.root / "source.part").exists())

    def test_valid_first_mirror_stops(self):
        run = self.download((SCRIPTS.parent / "data/v41-telegram-official-cidrs.txt").read_bytes(), b"<html>")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn(MIRROR, run.stdout)
        self.assertIn(PRIMARY, self.provenance.read_text())

    def test_optional_empty_response_keeps_explicit_degradation(self):
        mock = 'curl() { : > "${@: -2:1}"; }\n'
        run = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", self.helpers + mock + '\ndownload_optional_file "$@"',
             "_", "OPTIONAL", self.output.name, PRIMARY, "diagnostic-unavailable"],
            cwd=self.root, text=True, capture_output=True,
            env={**os.environ, "INPUT_PROVENANCE": str(self.provenance), "rir_reference_utc": REF},
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.output.read_text(), f"# Optional source unavailable during this build: {PRIMARY}\n")
        self.assertTrue(self.provenance.read_text().endswith("\t-\t0\tdiagnostic-unavailable\n"))


def tar_blob(name="as-ip-blocks-master/as/13335/aggregated.json", payload=None):
    data = io.BytesIO()
    if payload is None:
        payload = json.dumps({"asn": 13335, "metadata": {},
                              "prefixes": {"ipv4": ["192.0.2.0/24"], "ipv6": []}}).encode()
    with tarfile.open(fileobj=data, mode="w") as tar:
        member = tarfile.TarInfo(name)
        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))
    return data.getvalue()


class InputValidationTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "staged.part"

    def test_archive_requires_valid_gzip_tar_and_aggregate(self):
        valid = tar_blob()
        self.path.write_bytes(gzip.compress(valid))
        validate_ipverse(self.path, min_bytes=1, min_records=1)
        for bad in (
            gzip.compress(valid)[:-4],  # broken gzip footer
            gzip.compress(valid[:1024]),  # intact gzip wrapping truncated tar
            gzip.compress(valid[:1024] + b"x" * 512 + valid[1536:]),  # bad later tar header
            gzip.compress(tar_blob(payload=b'{"asn":13335,"prefixes":"not a mapping"}')),
            gzip.compress(tar_blob(name="root/../as/13335/aggregated.json")),
            gzip.compress(tar_blob(name="root/as/13335/not-the-expected-member")),
        ):
            with self.subTest(header=bad[:25], length=len(bad)):
                self.path.write_bytes(bad)
                with self.assertRaises((ValueError, OSError, EOFError, tarfile.TarError)):
                    validate_ipverse(self.path, min_bytes=1, min_records=1)

    def test_archive_enforces_expanded_limit_and_minimum_aggregate_count(self):
        self.path.write_bytes(gzip.compress(tar_blob()))
        for kwargs, pattern in (
            ({"min_records": 2}, "unique aggregate records"),
            ({"min_records": 1, "max_expanded": 128}, "expanded byte limit"),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, pattern):
                validate_ipverse(self.path, min_bytes=1, **kwargs)

    def test_cli_pinned_digest_is_checked_before_accepting_bytes(self):
        self.path.write_text("retained data\n")
        actual = hashlib.sha256(self.path.read_bytes()).hexdigest()
        command = ["python3", str(SCRIPTS / "validate_v41_download.py"), str(self.path), "--sha256"]
        self.assertEqual(subprocess.run(command + [actual], capture_output=True).returncode, 0)
        failed = subprocess.run(command + ["0" * 64], text=True, capture_output=True)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("pinned input SHA-256 mismatch", failed.stderr)
