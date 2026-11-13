import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from download_v41_locked_sources import fetch


class SourceLockTests(TestCase):
    def test_hash_and_provenance_are_fail_closed(self):
        with TemporaryDirectory() as td:
            r = Path(td)
            l = r / "lock.json"
            p = r / "provenance.tsv"
            entry = {"url": "https://github.com/a/b/releases/download/v1/geoip.dat",
                     "sha256": hashlib.sha256(b"good").hexdigest(), "bytes": 4}
            l.write_text(json.dumps({"test.dat": entry}))
            def download(cmd, check):
                Path(cmd[cmd.index("--output") + 1]).write_bytes(b"fake")
            with mock.patch("download_v41_locked_sources.subprocess.run", side_effect=download):
                with self.assertRaisesRegex(ValueError, "mismatch"):
                    fetch(l, p, r)
            self.assertFalse(p.exists())
            self.assertFalse((r / "test.dat").exists())
            entry["url"] = entry["url"].replace("/v1/", "/latest/")
            l.write_text(json.dumps({"test.dat": entry}))
            with mock.patch("download_v41_locked_sources.subprocess.run") as call:
                with self.assertRaisesRegex(ValueError, "unversioned"):
                    fetch(l, p, r)
                call.assert_not_called()
