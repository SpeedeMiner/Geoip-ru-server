import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent
FILES = ("geoip_RU.dat", "geoip_RU.srs", "geoip_PRIVATE.srs", "geoip_RU.mrs")


class CdnRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "release"
        self.work.mkdir()
        self.remote = self.root / "remote"
        self.git(self.root, "init", "-q", "--bare", str(self.remote))
        self.git(self.work, "init", "-q", "-b", "release")
        self.git(self.work, "config", "user.name", "Test")
        self.git(self.work, "config", "user.email", "test@example.test")
        for f in FILES:
            (self.work / f).write_bytes(f.encode() + b"\x00\xff")
            digest = hashlib.sha256((self.work / f).read_bytes()).hexdigest()
            (self.work / (f + ".sha256sum")).write_text(f"{digest}  {f}\n")
        (self.work / "quality.tsv").write_text("audit only\n")
        self.git(self.work, "add", "--all")
        self.git(self.work, "commit", "-qm", "fixture")
        self.git(self.work, "push", str(self.remote), "refs/heads/release")
        self.snapshot = self.git(self.remote, "rev-parse", "refs/heads/release")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        for f in ("repair_v41_cdn.sh", "v41_cdn_files.sh", "verify_v41_cdn_github_release.sh"):
            (self.scripts / f).write_bytes((SCRIPTS / f).read_bytes())
        (self.scripts / "deliver_v41_cdn.sh").write_text(
            '#!/bin/bash\nset -eu\n[[ "$V41_REQUIRE_CDN_READBACK" == 1 ]]\n'
            '[[ "$SNAPSHOT_SHA" == "$EXPECTED_SNAPSHOT" ]]\n'
            'out="$(mktemp -d)"\ntrap "rm -rf -- \\"$out\\"" EXIT\n'
            'bash "$(dirname "$0")/verify_v41_cdn_github_release.sh" "$SNAPSHOT_SHA" "$out"\n'
            'printf "%s\\n" "$SNAPSHOT_SHA" > "$TEST_DELIVERY"\n'
            'exit "${TEST_DELIVERY_STATUS:-0}"\n')
        mock = self.bin / "curl"
        mock.write_text(f"#!{sys.executable}\n" + r'''
import os,sys
from pathlib import Path
u=sys.argv[-1]
base="https://github.com/example/geoip/releases/download/latest-geoip-client-v41/"
assert u.startswith(base) and not "/" in u[len(base):]
name=u[len(base):]
with Path(os.environ["TEST_HTTP"]).open("a") as log: print(name,file=log)
if name==os.environ.get("TEST_MISSING"): sys.exit(22)
payload=(Path(os.environ["TEST_SOURCE"])/name).read_bytes()
if name==os.environ.get("TEST_MISMATCH"):payload=b"stale"
Path(sys.argv[sys.argv.index("--output")+1]).write_bytes(payload)
''')
        mock.chmod(0o700)
        self.delivered = self.root / "delivered"
        self.http = self.root / "http"
        self.env = {
            **os.environ, "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REPOSITORY": "example/geoip", "GITHUB_TOKEN": "fixture-only",
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{self.remote.as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_0": "https://github.com/example/geoip.git",
            "TEST_HTTP": str(self.http), "TEST_DELIVERY": str(self.delivered),
            "EXPECTED_SNAPSHOT": self.snapshot, "TEST_SOURCE": str(self.work),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
        }

    @staticmethod
    def git(directory, *args):
        return subprocess.check_output(["git", "-C", str(directory), *args],
                                       text=True, stderr=subprocess.PIPE).strip()

    def invoke(self, **opts):
        self.delivered.unlink(missing_ok=True)
        self.http.unlink(missing_ok=True)
        r = subprocess.run(["bash", str(self.scripts / "repair_v41_cdn.sh")],
                           cwd=self.root, env={**self.env, **opts}, capture_output=True, text=True)
        self.assertEqual(self.git(self.remote, "rev-parse", "refs/heads/release"), self.snapshot)
        self.assertEqual(self.git(self.remote, "tag", "--list"), "")
        return r

    def test_checks_only_exact_client_assets_before_delivery(self):
        r = self.invoke()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.delivered.read_text().strip(), self.snapshot)
        self.assertEqual(self.http.read_text().splitlines(),
                         [item for f in FILES for item in (f, f + ".sha256sum")])

    def test_missing_asset_stale_binary_and_stale_sidecar_fail_closed(self):
        for opts in ({"TEST_MISSING": FILES[2]},
                     {"TEST_MISMATCH": FILES[0]},
                     {"TEST_MISMATCH": FILES[1] + ".sha256sum"}):
            with self.subTest(opts=opts):
                r = self.invoke(**opts)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("CDN was not updated", r.stdout)
                self.assertFalse(self.delivered.exists())

    def test_non_main_and_automatic_invocation_fail_before_any_download(self):
        for opts in ({"GITHUB_REF": "refs/heads/feature"}, {"GITHUB_EVENT_NAME": "schedule"},
                     {"GITHUB_EVENT_NAME": "pull_request"}):
            with self.subTest(opts=opts):
                self.assertNotEqual(self.invoke(**opts).returncode, 0)
                self.assertFalse(self.delivered.exists())
                self.assertFalse(self.http.exists())

    def test_failed_cdn_readback_is_not_successful_repair(self):
        r = self.invoke(TEST_DELIVERY_STATUS="1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.delivered.read_text().strip(), self.snapshot)


if __name__ == "__main__":
    unittest.main()
