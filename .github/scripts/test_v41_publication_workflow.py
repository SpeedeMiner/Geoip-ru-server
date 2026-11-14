import gzip
from hashlib import sha256
import json
import random
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parent


class PublicationWorkflowTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.remote = self.root / "remote"
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.output = self.root / "output"
        self.repo = "example/geoip"
        self.env = {
            **os.environ, "PWD": str(self.root), "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{self.remote.as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_0": f"https://github.com/{self.repo}.git",
            "GITHUB_REPOSITORY": self.repo, "GITHUB_TOKEN": "test-only",
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_OUTPUT": str(self.output),
        }

    @staticmethod
    def git(*args, cwd):
        return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.PIPE).strip()

    def setup_git(self):
        self.git("init", "--bare", str(self.remote), cwd=self.root)
        seed = self.root / "seed"
        seed.mkdir()
        self.git("init", cwd=seed)
        self.git("symbolic-ref", "HEAD", "refs/heads/release", cwd=seed)
        (seed / "old").write_text("old", encoding="utf-8")
        self.git("add", "old", cwd=seed)
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.test",
                 "commit", "-m", "seed", cwd=seed)
        self.git("push", str(self.remote), "release", cwd=seed)
        self.env["PREVIOUS_RELEASE_SHA"] = self.git("rev-parse", "release", cwd=seed)
        script = (SCRIPTS / "publish_v41_git_refs.sh").read_text()
        for name in re.findall(r'"\$([A-Z_0-9]+)"', script.partition("for file in")[2].partition("; do")[0]):
            filename = name.lower()
            self.env[name] = filename
            (self.candidate / filename).write_text(filename, encoding="utf-8")
        (self.candidate / "geoip_RU_company_asn_registry.sha256sum").write_text("test", encoding="utf-8")

    def invoke(self, script, **env):
        return subprocess.run(["bash", str(SCRIPTS / script)], cwd=self.candidate,
                              env={**self.env, **env}, text=True, capture_output=True)

    def prepare_retained_archive(self):
        archive = gzip.compress(random.Random(42).randbytes(5_000_000), compresslevel=1, mtime=0)
        name = "as-ip-blocks.tar.gz"
        (self.candidate / name).write_bytes(archive)
        provenance = "geoip_RU_input_provenance.tsv"
        (self.candidate / provenance).write_text(
            "SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"
            "ipverse\tas-ip-blocks.tar.gz\thttps://example.test/archive\t"
            f"{sha256(archive).hexdigest()}\t{len(archive)}\tdownloaded\n"
        )
        self.env.update(IPVERSE_BGP_ARCHIVE=name, INPUT_PROVENANCE=provenance)
        self.asset = self.root / "published-archive"
        self.env.update(PATH=f"{self.root}:{os.environ['PATH']}", TEST_ASSET=str(self.asset))
        curl = self.root / "curl"
        curl.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, shutil, subprocess, sys\n"
            "tag = os.environ['SNAPSHOT_TAG']\n"
            "assert sys.argv[-1] == f'https://github.com/example/geoip/releases/download/{tag}/as-ip-blocks.tar.gz'\n"
            "asset = pathlib.Path(os.environ['TEST_ASSET'])\n"
            "if not asset.exists(): sys.exit(22)\n"
            "shutil.copyfile(asset, sys.argv[sys.argv.index('--output') + 1])\n"
            "if os.environ.get('COMPETING_SHA'):\n"
            "    subprocess.run(['git', '-C', os.environ['TEST_REMOTE'], 'update-ref', 'refs/heads/release',\n"
            "                    os.environ['COMPETING_SHA'], os.environ['PREVIOUS_RELEASE_SHA']], check=True)\n"
        )
        curl.chmod(0o700)
        return archive

    def stage(self, tag="v41.3"):
        self.output.unlink(missing_ok=True)
        result = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION=tag)
        self.assertEqual(result.returncode, 0, result.stderr)
        sha = self.git("rev-parse", f"refs/tags/{tag}", cwd=self.remote)
        self.assertEqual(self.output.read_text(), f"snapshot={tag}\nsnapshot_sha={sha}\n")
        self.env.update(SNAPSHOT_TAG=tag, SNAPSHOT_SHA=sha)
        return sha

    def test_tag_is_staged_without_moving_release_and_cannot_be_overwritten(self):
        self.setup_git()
        start = self.env["PREVIOUS_RELEASE_SHA"]
        target = self.stage()
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        self.assertEqual(self.git("rev-parse", "v41.3^", cwd=self.remote), start)
        self.assertEqual(self.git("show", "v41.3:v41_output_file", cwd=self.remote), "v41_output_file")
        self.assertEqual(self.git("show", "v41.3:geoip_RU_ipverse_snapshot_tag.txt",
                                  cwd=self.remote), "v41.3")
        (self.candidate / "v41_output_file").write_text("other candidate", encoding="utf-8")
        duplicate = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="v41.3")
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("already exists", duplicate.stdout)
        stale = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="v41.4", PREVIOUS_RELEASE_SHA=target)
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        self.assertEqual(self.git("rev-parse", "v41.3", cwd=self.remote), target)
        self.assertEqual(self.git("tag", "--list", cwd=self.remote), "v41.3")

    def test_scheduled_tag_and_invalid_manual_version(self):
        self.setup_git()
        invalid = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="latest-geoip-client-v41")
        self.assertNotEqual(invalid.returncode, 0)
        scheduled_manual = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="v41.3", GITHUB_EVENT_NAME="schedule")
        self.assertNotEqual(scheduled_manual.returncode, 0)
        auto = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="", GITHUB_EVENT_NAME="schedule")
        self.assertEqual(auto.returncode, 0, auto.stderr)
        target = self.git("rev-parse", "geoip-v41-snapshot-123.1", cwd=self.remote)
        self.assertEqual(self.output.read_text(), f"snapshot=geoip-v41-snapshot-123.1\nsnapshot_sha={target}\n")
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), self.env["PREVIOUS_RELEASE_SHA"])

    def test_release_does_not_advance_after_upload_failure_or_bad_readback(self):
        self.setup_git()
        archive = self.prepare_retained_archive()
        start = self.env["PREVIOUS_RELEASE_SHA"]
        target = self.stage()
        gh = self.root / "gh"
        gh.write_text("#!/bin/sh\nexit 1\n")
        gh.chmod(0o700)
        failed_upload = self.invoke("publish_v41_snapshot_release.sh")
        self.assertEqual(failed_upload.returncode, 1, failed_upload.stderr)
        missing = self.invoke("promote_v41_release.sh")
        self.assertEqual(missing.returncode, 22, missing.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        self.asset.write_bytes(archive[:-1] + bytes([archive[-1] ^ 1]))
        bad = self.invoke("promote_v41_release.sh")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("SHA-256 mismatch", bad.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        self.assertEqual(self.git("rev-parse", "v41.3", cwd=self.remote), target)

    def test_verified_asset_advances_only_to_the_staged_commit(self):
        self.setup_git()
        archive = self.prepare_retained_archive()
        start = self.env["PREVIOUS_RELEASE_SHA"]
        target = self.stage()
        gh = self.root / "gh"
        gh.write_text('#!/bin/sh\ncp as-ip-blocks.tar.gz "$TEST_ASSET"\n')
        gh.chmod(0o700)
        upload = self.invoke("publish_v41_snapshot_release.sh")
        self.assertEqual(upload.returncode, 0, upload.stderr)
        self.assertEqual(self.asset.read_bytes(), archive)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        wrong = self.invoke("promote_v41_release.sh", SNAPSHOT_SHA=start)
        self.assertNotEqual(wrong.returncode, 0)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        ok = self.invoke("promote_v41_release.sh")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), target)
        self.assertEqual(self.git("rev-parse", "release^", cwd=self.remote), start)

    def test_stale_snapshot_cannot_replace_a_competing_release(self):
        self.setup_git()
        archive = self.prepare_retained_archive()
        self.stage()
        saved = dict(self.env)
        other = self.stage("v41.4")
        self.asset.write_bytes(archive)
        ok = self.invoke("promote_v41_release.sh")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.env = saved
        stale = self.invoke("promote_v41_release.sh")
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), other)

    def test_branch_change_during_download_rejects_promotion(self):
        self.setup_git()
        archive = self.prepare_retained_archive()
        self.stage()
        saved = dict(self.env)
        other = self.stage("v41.4")
        self.env = saved
        self.asset.write_bytes(archive)
        result = self.invoke("promote_v41_release.sh", TEST_REMOTE=str(self.remote), COMPETING_SHA=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale info", result.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), other)

    def test_workflow_promotes_only_after_snapshot_upload_and_before_rolling_assets(self):
        workflow = (SCRIPTS.parent / "workflows" / "geoip-v41.yml").read_text()
        job = workflow.split("\n  publish:\n", 1)[1]
        steps = job.split("\n      - name: ")
        names = ("publish_v41_git_refs.sh", "publish_v41_snapshot_release.sh",
                 "promote_v41_release.sh", "tag_name: latest-geoip-client-v41")
        matches = [next(i for i, step in enumerate(steps) if name in step) for name in names]
        self.assertEqual(matches, sorted(set(matches)))
        for i in matches:
            self.assertNotRegex(steps[i], r"(?m)^\s+(if|continue-on-error):")

    def test_release_creation_requires_existing_tag_and_never_edits_on_failure(self):
        capture = self.root / "gh-log"
        gh = self.root / "gh"
        gh.write_text("#!/usr/bin/env python3\nimport json,os,sys\n"
                      "with open(os.environ['CAPTURE'], 'a') as log: log.write(json.dumps(sys.argv[1:])+'\\n')\n"
                      "sys.exit(1)\n", encoding="utf-8")
        gh.chmod(0o755)
        env = dict( SNAPSHOT_TAG="v41.3", CAPTURE=str(capture),
            PATH=f"{self.root}:{os.environ['PATH']}", V41_OUTPUT_FILE="geoip_RU.dat",
            OUTPUT_SHA_FILE="geoip_RU.dat.sha256sum", V41_MANIFEST="manifest.json",
            IPVERSE_BGP_ARCHIVE="as-ip-blocks.tar.gz", INPUT_PROVENANCE="inputs.tsv",
            V41_QUALITY_REPORT="quality.txt",
        )
        for field in ("V41_OUTPUT_FILE", "OUTPUT_SHA_FILE", "V41_MANIFEST", "IPVERSE_BGP_ARCHIVE"):
            (self.candidate / env[field]).write_text("asset", encoding="utf-8")
        archive_bytes = gzip.compress(random.Random(42).randbytes(5_000_000), compresslevel=1, mtime=0)
        (self.candidate / env["IPVERSE_BGP_ARCHIVE"]).write_bytes(archive_bytes)
        (self.candidate / env["INPUT_PROVENANCE"]).write_text(
            "SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"
            "ipverse\tas-ip-blocks.tar.gz\thttps://example.test/archive\t"
            f"{sha256(archive_bytes).hexdigest()}\t{len(archive_bytes)}\tdownloaded\n"
        )
        missing = self.invoke("publish_v41_snapshot_release.sh", **env)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("quality.txt", missing.stderr)
        self.assertFalse(capture.exists())
        (self.candidate / env["V41_QUALITY_REPORT"]).touch()
        empty = self.invoke("publish_v41_snapshot_release.sh", **env)
        self.assertNotEqual(empty.returncode, 0)
        self.assertFalse(capture.exists())
        (self.candidate / env["V41_QUALITY_REPORT"]).write_text("asset", encoding="utf-8")
        (self.candidate / env["IPVERSE_BGP_ARCHIVE"]).write_bytes(archive_bytes[:-1])
        mismatch = self.invoke("publish_v41_snapshot_release.sh", **env)
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("size mismatch", mismatch.stderr)
        self.assertFalse(capture.exists())
        (self.candidate / env["IPVERSE_BGP_ARCHIVE"]).write_bytes(archive_bytes)
        result = self.invoke("publish_v41_snapshot_release.sh", **env)
        self.assertNotEqual(result.returncode, 0)
        command, = [json.loads(row) for row in capture.read_text().splitlines()]
        self.assertEqual(command[:3], ["release", "create", "v41.3"])
        self.assertIn("as-ip-blocks.tar.gz", command)
        self.assertIn("--verify-tag", command)
        self.assertIn("--latest=false", command)


if __name__ == "__main__":
    unittest.main()
