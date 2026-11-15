import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent
FILES = ("geoip_RU.dat", "geoip_RU.srs", "geoip_PRIVATE.srs")


class CdnPublicationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.release = self.root / "release"
        self.release.mkdir()
        self.remote = self.root / "remote.git"
        self.output = self.root / "output"
        self.git(self.root, "init", "-q", "--bare", str(self.remote))
        self.git(self.release, "init", "-q", "-b", "release")
        self.git(self.release, "config", "user.name", "Test")
        self.git(self.release, "config", "user.email", "test@example.test")
        self.env = {
            **os.environ,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_TOKEN": "test-only",
            "GITHUB_REPOSITORY": "example/geoip",
            "GITHUB_OUTPUT": str(self.output),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{self.remote.as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_0": "https://github.com/example/geoip.git",
        }
        self.initial_release = self.make_release(b"initial")

    @staticmethod
    def git(directory, *args):
        return subprocess.check_output(["git", "-C", str(directory), *args],
                                       stderr=subprocess.PIPE)

    def make_release(self, suffix, *, bad_checksum=False, missing=None):
        for name in FILES:
            p = self.release / name
            if name == missing:
                p.unlink(missing_ok=True)
                continue
            data = name.encode() + b"\0\xff" + suffix
            p.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            (self.release / (name + ".sha256sum")).write_text(
                f"{'0' * 64 if bad_checksum else digest}  {name}\n")
        for name in ("audit.tsv", "manifest.json", "hydra-geoip.dat", "unlisted.srs"):
            (self.release / name).write_text("not client content\n")
        self.git(self.release, "add", "--all")
        self.git(self.release, "commit", "-qm", "release " + suffix.decode())
        self.git(self.release, "push", str(self.remote), "refs/heads/release")
        return self.git(self.remote, "rev-parse", "refs/heads/release").decode().strip()

    def invoke(self, sha=None, **options):
        self.output.unlink(missing_ok=True)
        return subprocess.run(["bash", str(SCRIPTS / "publish_v41_cdn_branch.sh")],
                              cwd=self.root, capture_output=True, text=True,
                              env={**self.env, "SNAPSHOT_SHA": sha or self.initial_release, **options})

    def cdn(self):
        return self.git(self.remote, "rev-parse", "refs/heads/cdn").decode().strip()

    def check_tree(self, release):
        self.assertEqual(set(self.git(self.remote, "ls-tree", "-r", "--name-only", self.cdn())
                             .decode().splitlines()), set(FILES))
        for name in FILES:
            self.assertEqual(self.git(self.remote, "show", f"{self.cdn()}:{name}"),
                             self.git(self.remote, "show", f"{release}:{name}"))

    def test_only_exact_client_payload_root_then_fast_forward_and_noop(self):
        self.assertEqual(self.invoke().returncode, 0)
        first = self.cdn()
        self.assertEqual(self.git(self.remote, "rev-list", "--parents", "-n", "1", first)
                         .decode().split(), [first])
        self.check_tree(self.initial_release)
        changed = self.make_release(b"next")
        request = self.invoke(changed)
        self.assertEqual(request.returncode, 0, request.stderr)
        self.assertEqual(self.git(self.remote, "rev-list", "--parents", "-n", "1", self.cdn())
                         .decode().split(), [self.cdn(), first])
        self.check_tree(changed)
        head = self.cdn()
        repeated = self.invoke(changed)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertIn("unchanged", repeated.stdout)
        self.assertEqual(self.cdn(), head)
        self.assertEqual(self.output.read_text(), f"cdn_sha={head}\n")
        self.assertEqual(self.git(self.remote, "rev-parse", "refs/heads/release").decode().strip(),
                         changed)
        self.assertFalse(self.git(self.remote, "tag", "--list"))

    def test_invalid_snapshot_or_checksum_cannot_move_cdn(self):
        self.assertEqual(self.invoke().returncode, 0)
        head = self.cdn()
        bad = self.make_release(b"bad", bad_checksum=True)
        for sha in (self.initial_release, bad):
            self.assertNotEqual(self.invoke(sha).returncode, 0)
            self.assertEqual(self.cdn(), head)
        incomplete = self.make_release(b"missing", missing=FILES[2])
        self.assertNotEqual(self.invoke(incomplete).returncode, 0)
        self.assertEqual(self.cdn(), head)

    def test_rejects_non_main_and_contaminated_existing_cdn(self):
        for ref, event in (("refs/heads/other", "push"), ("refs/heads/main", "pull_request")):
            self.assertNotEqual(self.invoke(GITHUB_REF=ref, GITHUB_EVENT_NAME=event).returncode, 0)
        self.assertFalse(self.git(self.remote, "branch", "--list", "cdn"))
        self.git(self.remote, "update-ref", "refs/heads/cdn", self.initial_release)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected files", result.stdout)
        self.assertEqual(self.cdn(), self.initial_release)

    def test_symlink_with_matching_checksum_is_not_a_client_blob(self):
        suspect = self.release / FILES[0]
        suspect.unlink()
        suspect.symlink_to("audit.tsv")
        digest = hashlib.sha256(b"audit.tsv").hexdigest()
        (self.release / (FILES[0] + ".sha256sum")).write_text(
            f"{digest}  {FILES[0]}\n")
        self.git(self.release, "add", "--all")
        self.git(self.release, "commit", "-qm", "symlink")
        self.git(self.release, "push", str(self.remote), "refs/heads/release")
        sha = self.git(self.release, "rev-parse", "HEAD").decode().strip()
        self.assertNotEqual(self.invoke(sha).returncode, 0)
        self.assertFalse(self.git(self.remote, "branch", "--list", "cdn"))

    def test_lease_refuses_to_overwrite_parallel_update(self):
        self.assertEqual(self.invoke().returncode, 0)
        prior = self.cdn()
        current_release = self.make_release(b"concurrent")
        tree = self.git(self.remote, "rev-parse", prior + "^{tree}").decode().strip()
        rival = self.git(self.remote, "-c", "user.name=Rival", "-c", "user.email=r@example.test",
                         "commit-tree", tree, "-p", prior, "-m", "Concurrent CDN change").decode().strip()
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        git = bin_dir / "git"
        import shutil
        real_git = shutil.which("git")
        git.write_text(f"#!{sys.executable}\n"
                       "import os,subprocess,sys\n"
                       f"git={real_git!r}\n"
                       "if '--force-with-lease=refs/heads/cdn:' + os.environ['TEST_PRIOR'] in sys.argv:\n"
                       " subprocess.run([git,'-C',os.environ['TEST_REMOTE'],'update-ref','refs/heads/cdn',"
                       "os.environ['TEST_RIVAL'],os.environ['TEST_PRIOR']],check=True)\n"
                       "os.execv(git,[git,*sys.argv[1:]])\n")
        git.chmod(0o700)
        result = self.invoke(current_release, PATH=f"{bin_dir}:{os.environ['PATH']}",
                             TEST_PRIOR=prior, TEST_REMOTE=str(self.remote), TEST_RIVAL=rival)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale info", result.stderr)
        self.assertEqual(self.cdn(), rival)
        self.assertFalse(self.output.exists())


class CdnReadbackTests(unittest.TestCase):
    def invoke(self, *, mismatch=None, transient=False, raw_timeout=False, mode=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for filename in FILES:
                (root / filename).write_text(filename)
            curl = root / "curl"
            curl.write_text(f"#!{sys.executable}\n" + r'''
import os,sys
from pathlib import Path
from urllib.parse import urlsplit
url=urlsplit(sys.argv[-1])
filename=url.path.rsplit("/",1)[1]
assert filename in ("geoip_RU.dat", "geoip_RU.srs", "geoip_PRIVATE.srs")
with Path("calls").open("a") as f:
    print(url.netloc, filename, file=f)
assert url.netloc in ("raw.githubusercontent.com", "cdn.jsdelivr.net")
assert ("@cdn/" in url.path) == (url.netloc == "cdn.jsdelivr.net")
out=Path(sys.argv[sys.argv.index("--output")+1])
if url.netloc == "raw.githubusercontent.com" and filename=="geoip_RU.dat":
    raw_timeout=os.environ["TEST_RAW_TIMEOUT"]
    if raw_timeout=="always" or raw_timeout=="once" and not Path("raw-retried").exists():
        Path("raw-retried").touch()
        sys.exit(28)
stale=os.environ.get("TEST_MISMATCH")==filename and url.netloc=="cdn.jsdelivr.net"
if stale and os.environ.get("TEST_TRANSIENT")=="1":
    stale=not Path("retried").exists()
    Path("retried").touch()
out.write_text("stale" if stale else filename)
''')
            curl.chmod(0o700)
            sleep = root / "sleep"
            sleep.write_text("#!/bin/sh\nexit 0\n")
            sleep.chmod(0o700)
            args = [] if mode is None else [mode]
            p = subprocess.run(["bash", str(SCRIPTS / "verify_v41_cdn_readback.sh"), *args],
                               cwd=root, capture_output=True, text=True, env={
                **os.environ, "PATH": f"{root}:{os.environ['PATH']}",
                "GITHUB_REPOSITORY": "example/geoip", "CDN_SHA": "a" * 40,
                "TEST_MISMATCH": mismatch or "", "TEST_TRANSIENT": str(int(transient)),
                "TEST_RAW_TIMEOUT": raw_timeout or ""})
            log = root / "calls"
            return p, log.read_text().splitlines() if log.exists() else []

    def test_correct_bytes_for_every_client_file(self):
        r, calls = self.invoke()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(calls), 6)
        self.assertTrue(all("sha256" not in line for line in calls))

    def test_cdn_retries_stale_bytes_and_reports_persistent_mismatch(self):
        r, calls = self.invoke(mismatch=FILES[0], transient=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(calls), 7)
        r, calls = self.invoke(mismatch=FILES[0])
        self.assertEqual(r.returncode, 1)
        self.assertIn("Use GitHub Release", r.stdout)
        self.assertEqual(len(calls), 8)
        self.assertTrue(calls[-1].endswith(FILES[-1]))


    def test_pinned_raw_retries_transient_transport_error_but_fails_closed(self):
        r, calls = self.invoke(raw_timeout="once")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(calls), 7)
        self.assertEqual(calls[:2], ["raw.githubusercontent.com geoip_RU.dat"] * 2)
        r, calls = self.invoke(raw_timeout="always")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls, ["raw.githubusercontent.com geoip_RU.dat"] * 3)
        self.assertIn("bytes not confirmed after retries", r.stdout)

    def test_pinned_mode_and_public_mode_are_separate(self):
        for mode, hostname in (("pinned", "raw.githubusercontent.com"), ("public", "cdn.jsdelivr.net")):
            with self.subTest(mode=mode):
                r, calls = self.invoke(mode=mode)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(calls, [f"{hostname} {f}" for f in FILES])
        r, calls = self.invoke(mode="typo")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(calls, [])


class DeliveryStepTests(unittest.TestCase):
    def invoke(self, *, publish_status=0, purge_status=0, readback_status=0, strict=False,
               github_status=0, pinned_status=0):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delivery = root / "deliver_v41_cdn.sh"
            delivery.write_bytes((SCRIPTS / delivery.name).read_bytes())
            (root / "verify_v41_cdn_github_release.sh").write_text(
                'echo github >> "$CALLS"\n[[ "$1" == "$TEST_SHA" && -d "$2" ]] || exit 91\n'
                'exit "$GITHUB_STATUS"\n')
            (root / "publish_v41_cdn_branch.sh").write_text(
                'echo publish >> "$CALLS"\nprintf "cdn_sha=%s\\n" "$TEST_SHA" >>"$GITHUB_OUTPUT"\n'
                'exit "$PUBLISH_STATUS"\n')
            (root / "purge_v41_jsdelivr.sh").write_text('echo purge >> "$CALLS"\nexit "$PURGE_STATUS"\n')
            (root / "verify_v41_cdn_readback.sh").write_text(
                'echo "${1:-missing-mode}" >> "$CALLS"\n[[ "$CDN_SHA" == "$TEST_SHA" ]] || exit 92\n'
                'case "${1:-}" in pinned) exit "$PINNED_STATUS" ;; public) exit "$READBACK_STATUS" ;; *) exit 93 ;; esac\n')
            calls, outputs = root / "calls", root / "outputs"
            sha = "1" * 40
            result = subprocess.run(["bash", str(delivery)], text=True, capture_output=True,
                                    env={**os.environ, "TEST_SHA": sha, "CALLS": str(calls),
                                         "GITHUB_OUTPUT": str(outputs), "PUBLISH_STATUS": str(publish_status),
                                         "PURGE_STATUS": str(purge_status), "READBACK_STATUS": str(readback_status),
                                         "PINNED_STATUS": str(pinned_status),
                                         "V41_REQUIRE_CDN_READBACK": str(int(strict)),
                                         "GITHUB_STATUS": str(github_status), "SNAPSHOT_SHA": sha})
            return result, calls.read_text().splitlines(), outputs.read_text() if outputs.exists() else None

    def test_required_ref_write_and_independent_best_effort_cache_steps(self):
        res, calls, out = self.invoke(purge_status=1, readback_status=1)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(calls, ["github", "publish", "pinned", "purge", "public"])
        self.assertEqual(out, f"cdn_sha={'1' * 40}\n")
        self.assertIn("not confirmed", res.stdout)
        failure, calls, out = self.invoke(publish_status=1)
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(calls, ["github", "publish"])
        self.assertIsNone(out)

    def test_manual_repair_requires_cdn_bytes_but_not_a_purge_confirmation(self):
        res, calls, out = self.invoke(purge_status=1, strict=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(calls, ["github", "publish", "pinned", "purge", "public"])
        self.assertEqual(out, f"cdn_sha={'1' * 40}\n")
        failure, calls, out = self.invoke(readback_status=1, strict=True)
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(calls, ["github", "publish", "pinned", "purge", "public"])
        self.assertIn("is set, but public CDN bytes were not confirmed", failure.stdout)
        self.assertIsNone(out)


    def test_unconfirmed_pinned_origin_never_refreshes_public_cache(self):
        for strict in (False, True):
            with self.subTest(strict=strict):
                res, calls, out = self.invoke(pinned_status=1, strict=strict)
                self.assertEqual(res.returncode, int(strict), res.stderr)
                self.assertEqual(calls, ["github", "publish", "pinned"])
                self.assertIn("skipping jsDelivr purge", res.stdout)
                self.assertEqual(out, None if strict else f"cdn_sha={'1' * 40}\n")

    def test_github_preflight_failure_stops_production_and_repair(self):
        for strict in (False, True):
            with self.subTest(strict=strict):
                res, calls, out = self.invoke(github_status=1, strict=strict)
                self.assertEqual(res.returncode, 1)
                self.assertEqual(calls, ["github"])
                self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
