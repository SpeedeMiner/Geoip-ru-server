from datetime import date
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


from validate_v41_download_input import validate, validate_ipverse


SCRIPTS = Path(__file__).resolve().parent
REF = "2026-09-01"
PRIMARY = "https://first.test/feed"
MIRROR = "https://second.test/feed"


def delegated(registry="apnic", date="20260901"):
    return (
        f"2|{registry}|12345|3|20260101|{date}|+0000\n"
        f"{registry}|*|asn|*|1|summary\n"
        f"{registry}|*|ipv4|*|1|summary\n"
        f"{registry}|*|ipv6|*|1|summary\n"
        f"{registry}|AU|asn|13335|1|20260101|allocated\n"
        f"{registry}|AU|ipv4|192.0.2.0|256|20260101|allocated\n"
        f"{registry}|AU|ipv6|2001:db8::|32|20260101|allocated\n"
    ).encode()


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
        self.helpers = script[script.index("record_source_download()"):script.index("# Use one UTC reference")]

    def download(self, first, second, profile="rir:apnic"):
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
             "_", "MIRROR SAMPLE", self.output.name, profile, PRIMARY, MIRROR],
            cwd=self.root, text=True, capture_output=True,
            env={**os.environ, "INPUT_PROVENANCE": str(self.provenance), "rir_reference_utc": REF},
        )

    def test_http_success_with_html_tries_next_mirror_and_records_only_valid_url(self):
        valid = delegated()
        run = self.download(b"<!doctype html><html>Upstream unavailable</html>", valid)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.output.read_bytes(), valid)
        self.assertEqual(self.provenance.read_text().splitlines(), [
            f"MIRROR SAMPLE\tsource\t{MIRROR}\t{hashlib.sha256(valid).hexdigest()}\t{len(valid)}\tdownloaded"
        ])
        self.assertFalse((self.root / "source.part").exists())

    def test_stale_wrong_registry_or_empty_mirror_falls_through(self):
        for bad in (delegated(date="20260817"), delegated(registry="arin"), delegated()[:-53], b""):
            with self.subTest(bad=bad[:35]):
                self.provenance.write_text("")
                run = self.download(bad, delegated())
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(self.output.read_bytes(), delegated())
                self.assertIn(MIRROR, self.provenance.read_text())
                self.assertNotIn(PRIMARY, self.provenance.read_text())

    def test_required_all_invalid_fails_even_if_old_output_exists(self):
        run = self.download(b"<html>", b"")
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertEqual(self.provenance.read_text(), "")
        self.assertEqual(self.output.read_bytes(), b"previous run")
        self.assertFalse((self.root / "source.part").exists())

    def test_valid_first_mirror_stops(self):
        run = self.download(delegated(), b"<html>")
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

    def test_csv_must_parse_with_expected_schema_families_and_content(self):
        self.path.write_text("Address Block,Globally Reachable\n192.0.2.0/24,False\n192.0.0.9/32,True\n")
        validate(self.path, "iana:4", date.fromisoformat(REF))
        for profile, payload in (
            ("iana:6", self.path.read_text()),
            ("iana:4", "Address Block,Globally Reachable\n"),
            ("iana:4", "incorrect,header\n192.0.2.0/24,False\n"),
            ("iana:4", "<html>login required</html>\n"),
        ):
            self.path.write_text(payload)
            with self.subTest(profile=profile, payload=payload), self.assertRaises(ValueError):
                validate(self.path, profile, date.fromisoformat(REF))

    def test_lacnic_asn_summary_shortfall_does_not_hide_ip_truncation(self):
        valid = delegated("lacnic").replace(b"|12345|3|", b"|12345|4|").replace(b"|asn|*|1|summary", b"|asn|*|2|summary")
        self.path.write_bytes(valid)
        validate(self.path, "rir:lacnic", date.fromisoformat(REF))
        self.path.write_bytes(valid.replace(b"|ipv6|*|1|summary", b"|ipv6|*|2|summary").replace(b"|12345|4|", b"|12345|5|"))
        with self.assertRaisesRegex(ValueError, "ipv6 rows"):
            validate(self.path, "rir:lacnic", date.fromisoformat(REF))

    def test_pinned_download_is_validated_against_its_existing_digest(self):
        self.path.write_bytes(b"immutable payload")
        ref = date.fromisoformat(REF)
        profile = "sha256:" + hashlib.sha256(self.path.read_bytes()).hexdigest()
        validate(self.path, profile, ref)
        self.path.write_bytes(b"mutated payload")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validate(self.path, profile, ref)
