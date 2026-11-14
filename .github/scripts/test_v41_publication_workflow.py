import json
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

    def test_manual_release_is_fast_forward_and_cannot_overwrite_tag(self):
        self.setup_git()
        start = self.env["PREVIOUS_RELEASE_SHA"]
        result = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="v41.3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_text(), "snapshot=v41.3\n")
        target = self.git("rev-parse", "release", cwd=self.remote)
        self.assertEqual(self.git("rev-parse", "v41.3", cwd=self.remote), target)
        self.assertEqual(self.git("rev-parse", "release^", cwd=self.remote), start)
        self.assertEqual(self.git("show", "v41.3:v41_output_file", cwd=self.remote), "v41_output_file")
        (self.candidate / "v41_output_file").write_text("other candidate", encoding="utf-8")
        duplicate = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="v41.3", PREVIOUS_RELEASE_SHA=target)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("already exists", duplicate.stdout)
        stale = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="v41.4")
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), target)
        self.assertEqual(self.git("tag", "--list", cwd=self.remote), "v41.3")

    def test_scheduled_tag_and_invalid_manual_version(self):
        self.setup_git()
        invalid = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="latest-geoip-client-v41")
        self.assertNotEqual(invalid.returncode, 0)
        scheduled_manual = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="v41.3", GITHUB_EVENT_NAME="schedule")
        self.assertNotEqual(scheduled_manual.returncode, 0)
        auto = self.invoke("publish_v41_git_refs.sh", SNAPSHOT_VERSION="", GITHUB_EVENT_NAME="schedule")
        self.assertEqual(auto.returncode, 0, auto.stderr)
        self.assertEqual(self.output.read_text(), "snapshot=geoip-v41-snapshot-123.1\n")

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
            V41_QUALITY_REPORT="quality.txt",
        )
        for field in ("V41_OUTPUT_FILE", "OUTPUT_SHA_FILE", "V41_MANIFEST"):
            (self.candidate / env[field]).write_text("asset", encoding="utf-8")
        missing = self.invoke("publish_v41_snapshot_release.sh", **env)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("quality.txt", missing.stderr)
        self.assertFalse(capture.exists())
        (self.candidate / env["V41_QUALITY_REPORT"]).touch()
        empty = self.invoke("publish_v41_snapshot_release.sh", **env)
        self.assertNotEqual(empty.returncode, 0)
        self.assertFalse(capture.exists())
        (self.candidate / env["V41_QUALITY_REPORT"]).write_text("asset", encoding="utf-8")
        result = self.invoke("publish_v41_snapshot_release.sh", **env)
        self.assertNotEqual(result.returncode, 0)
        command, = [json.loads(row) for row in capture.read_text().splitlines()]
        self.assertEqual(command[:3], ["release", "create", "v41.3"])
        self.assertIn("--verify-tag", command)
        self.assertIn("--latest=false", command)


if __name__ == "__main__":
    unittest.main()
