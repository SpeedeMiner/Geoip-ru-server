"""Exercise the real CDN shell chain against a local Git remote and fake HTTP."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent
FILES = ("geoip_RU.dat", "geoip_RU.srs", "geoip_PRIVATE.srs")
ORIGIN = "https://github.com/example/geoip.git"
REF = "refs/heads/cdn"
TAG = "geoip-v41-snapshot-42.1"


class DeliveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.remote = self.root / "remote"
        self.work = self.root / "work"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.git(self.root, "init", "-q", "--bare", str(self.remote))
        self.git(self.root, "init", "-q", "-b", "release", str(self.work))
        self.git(self.work, "config", "user.name", "Fixture")
        self.git(self.work, "config", "user.email", "fixture@example.test")
        for name in FILES:
            data = name.encode() + b"\0\xff"
            (self.work / name).write_bytes(data)
            (self.work / (name + ".sha256sum")).write_text(
                f"{hashlib.sha256(data).hexdigest()}  {name}\n")
        for name in ("geoip_RU_v41_manifest.json", "hydra-geoip.dat", "other.srs", "journal.md"):
            (self.work / name).write_text("not a supported CDN asset\n")
        self.git(self.work, "add", "--all")
        self.git(self.work, "commit", "-qm", "validated release")
        self.git(self.work, "tag", TAG)
        self.git(self.work, "push", str(self.remote), "refs/heads/release", f"refs/tags/{TAG}")
        self.release = self.git(self.remote, "rev-parse", "refs/heads/release").strip().decode()
        self.write_fixture("sleep", "#!/bin/sh\nexit 0\n")
        self.write_fixture("curl", f"#!{sys.executable}\n" + r'''
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

files = {"geoip_RU.dat", "geoip_RU.srs", "geoip_PRIVATE.srs"}
url = urlsplit(sys.argv[-1])
assert url.scheme == "https" and not url.query and not url.fragment
name = url.path.rsplit("/", 1)[1]
host = url.netloc
mode = os.environ["CASE"]
log = Path(os.environ["LOG"])
with log.open("a") as stream:
    print(host, name, file=stream)
if host == "github.com":
    assert url.path == "/example/geoip/releases/download/latest-geoip-client-v41/" + name
    assert name.removesuffix(".sha256sum") in files
    data = (Path(os.environ["RELEASE_FILES"]) / name).read_bytes()
    if mode == "bad-rolling" and name == "geoip_RU.srs.sha256sum":
        data = b"stale sidecar"
elif host == "purge.jsdelivr.net":
    assert url.path == "/gh/example/geoip@cdn/" + name and name in files
    if mode == "purge-down":
        sys.exit(22)
    print(json.dumps({"status":"finished","paths":{
        url.path: {"throttled":False,"providers":{"fixture":True}}}}))
    sys.exit(0)
elif host in ("raw.githubusercontent.com", "cdn.jsdelivr.net"):
    assert name in files
    if host == "raw.githubusercontent.com":
        ref = url.path.split("/")[-2]
        assert url.path == "/example/geoip/" + ref + "/" + name
        assert len(ref) == 40
        if mode == "raw-down" and name == "geoip_RU.dat":
            sys.exit(28)
        if mode == "raw-lag" and name == "geoip_RU.dat":
            mark = log.with_suffix(".raw-retried")
            if not mark.exists():
                mark.touch()
                sys.exit(22)
    else:
        assert url.path == "/gh/example/geoip@cdn/" + name
        ref = "refs/heads/cdn"
    data = subprocess.check_output(["git", "-C", os.environ["REMOTE"], "show", ref + ":" + name])
    if host == "cdn.jsdelivr.net" and mode == "stale-cdn" and name == "geoip_RU.srs":
        data = b"old CDN bytes"
else:
    raise AssertionError("unexpected HTTP request " + url.geturl())
Path(sys.argv[sys.argv.index("--output") + 1]).write_bytes(data)
''')

    def write_fixture(self, name, body):
        p = self.bin / name
        p.write_text(body)
        p.chmod(0o700)

    @staticmethod
    def git(directory, *args):
        return subprocess.check_output(["git", "-C", str(directory), *args], stderr=subprocess.PIPE)

    def invoke(self, mode, *, manual=False):
        log, out, summary = [self.root / n for n in ("http", "out", "summary")]
        for path in (log, out, summary, log.with_suffix(".raw-retried")):
            path.unlink(missing_ok=True)
        script = "repair_v41_cdn.sh" if manual else "deliver_v41_cdn.sh"
        args = {
            **os.environ, "CASE": mode, "LOG": str(log), "RELEASE_FILES": str(self.work),
            "REMOTE": str(self.remote), "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summary),
            "GITHUB_REPOSITORY": "example/geoip", "GITHUB_REF": "refs/heads/main",
            "GITHUB_TOKEN": "fixture-only", "SNAPSHOT_SHA": self.release,
            "GITHUB_EVENT_NAME": "workflow_dispatch" if manual else "schedule",
            "V41_CDN_FALLBACK_TAG": "" if manual else TAG,
            "V41_REQUIRE_CDN_READBACK": "0",
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{self.remote.as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_0": ORIGIN, "PATH": f"{self.bin}:{os.environ['PATH']}",
        }
        result = subprocess.run(["bash", str(SCRIPTS / script)], cwd=self.root, env=args,
                                capture_output=True, text=True, timeout=30)
        # Both entry points are scoped to refs/heads/cdn.
        self.assertEqual(self.git(self.remote, "rev-parse", "refs/heads/release").strip().decode(),
                         self.release)
        self.assertEqual(self.git(self.remote, "tag", "--list").strip().decode(), TAG)
        return result, log.read_text().splitlines(), out.read_text() if out.exists() else "", (
            summary.read_text() if summary.exists() else "")

    def cdn(self):
        return self.git(self.remote, "rev-parse", REF).strip().decode()

    def test_scheduled_delivers_only_client_files_after_pinned_origin_recovers(self):
        run, calls, output, summary = self.invoke("raw-lag")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual([line.split()[0] for line in calls],
                         ["github.com"] * 6 + ["raw.githubusercontent.com"] * 4
                         + ["purge.jsdelivr.net"] * 3 + ["cdn.jsdelivr.net"] * 3)
        self.assertEqual(output, f"cdn_sha={self.cdn()}\ncdn_status=verified\n")
        self.assertIn(f"/releases/tag/{TAG}", summary)
        self.assertEqual(self.git(self.remote, "ls-tree", "-r", "--name-only", REF)
                         .decode().splitlines(), sorted(FILES))
        for name in FILES:
            self.assertEqual(self.git(self.remote, "show", f"{REF}:{name}"),
                             self.git(self.remote, "show", f"{self.release}:{name}"))

    def test_invalid_rolling_asset_never_creates_or_overwrites_cdn(self):
        blocked, calls, output, _ = self.invoke("bad-rolling")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(output, "")
        self.assertTrue(all(s.startswith("github.com ") for s in calls))
        self.assertFalse(self.git(self.remote, "branch", "--list", "cdn"))
        self.assertEqual(self.invoke("ok")[0].returncode, 0)
        before = self.cdn()
        self.assertNotEqual(self.invoke("bad-rolling")[0].returncode, 0)
        self.assertEqual(self.cdn(), before)

    def test_manual_repair_is_strict_but_reusing_a_valid_ref_is_idempotent(self):
        blocked, calls, output, _ = self.invoke("raw-down", manual=True)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(output, "")
        self.assertEqual(calls[-3:], ["raw.githubusercontent.com geoip_RU.dat"] * 3)
        self.assertTrue(all(".jsdelivr.net " not in s for s in calls))
        before = self.cdn()
        stale, calls, output, _ = self.invoke("stale-cdn", manual=True)
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(output, "")
        self.assertEqual(calls.count("cdn.jsdelivr.net geoip_RU.srs"), 3)
        ready, _, output, summary = self.invoke("purge-down", manual=True)
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.assertEqual(self.cdn(), before)
        self.assertEqual(output, f"cdn_sha={before}\ncdn_status=verified\n")
        self.assertIn("cache purge not confirmed", summary)
        self.assertIn("/releases/tag/latest-geoip-client-v41", summary)


if __name__ == "__main__":
    unittest.main()
