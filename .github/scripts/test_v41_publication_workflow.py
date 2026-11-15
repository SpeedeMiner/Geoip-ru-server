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


from bundle_v41_registry_inputs import BLOCK_MEMBERS, MEMBERS, create
from v41_release_manifest import CORE, MANIFEST, SNAPSHOT, make


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

    def prepare_srs_assets(self):
        for name in ("geoip_RU.srs", "geoip_PRIVATE.srs"):
            (self.candidate / name).write_text(name, encoding="ascii")
            (self.candidate / (name + ".sha256sum")).write_text("fixture", encoding="ascii")

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
        self.prepare_srs_assets()

    def invoke(self, script, **env):
        return subprocess.run(["bash", str(SCRIPTS / script)], cwd=self.candidate,
                              env={**self.env, **env}, text=True, capture_output=True)

    def prepare_retained_archive(self):
        archive = gzip.compress(random.Random(42).randbytes(5_000_000), compresslevel=1, mtime=0)
        name = "as-ip-blocks.tar.gz"
        (self.candidate / name).write_bytes(archive)
        self.prepare_registry(provenance="geoip_RU_input_provenance.tsv", ipverse=archive)
        self.env["IPVERSE_BGP_ARCHIVE"] = name
        self.asset = self.root / "published-archive"
        self.registry_asset = self.root / "published-registry"
        self.env.update(PATH=f"{self.root}:{os.environ['PATH']}", TEST_ASSET=str(self.asset),
                        TEST_REGISTRY_ASSET=str(self.registry_asset),
                        TEST_UPSTREAM_ASSET=str(self.root / "published-upstream"),
                        TEST_PUBLIC=str(self.root / "public-snapshot"))
        curl = self.root / "curl"
        curl.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, shutil, subprocess, sys\n"
            "tag = os.environ['SNAPSHOT_TAG']\n"
            "base = f'https://github.com/example/geoip/releases/download/{tag}/'\n"
            "assert sys.argv[-1].startswith(base)\n"
            "name = sys.argv[-1][len(base):]\n"
            "key = {'as-ip-blocks.tar.gz':'TEST_ASSET','v41-registry-inputs.tar.gz':'TEST_REGISTRY_ASSET','v41-upstream-inputs.tar.gz':'TEST_UPSTREAM_ASSET'}.get(name)\n"
            "asset = pathlib.Path(os.environ[key]) if key else pathlib.Path(os.environ['TEST_PUBLIC']) / name\n"
            "if not asset.exists(): sys.exit(22)\n"
            "shutil.copyfile(asset, sys.argv[sys.argv.index('--output') + 1])\n"
            "if key == 'TEST_ASSET' and os.environ.get('COMPETING_SHA'):\n"
            "    subprocess.run(['git', '-C', os.environ['TEST_REMOTE'], 'update-ref', 'refs/heads/release',\n"
            "                    os.environ['COMPETING_SHA'], os.environ['PREVIOUS_RELEASE_SHA']], check=True)\n"
        )
        curl.chmod(0o700)
        return archive

    def prepare_registry(self, provenance, ipverse):
        bundle = "v41-registry-inputs.tar.gz"
        checksum = "geoip_RU_v41_registry_inputs.sha256sum"
        rows = ["SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS",
                f"ipverse\tas-ip-blocks.tar.gz\thttps://example.test/archive\t"
                f"{sha256(ipverse).hexdigest()}\t{len(ipverse)}\tdownloaded"]
        for member in MEMBERS:
            data = member.encode("ascii")
            (self.candidate / member).write_bytes(data)
            rows.append(f"registry\t{member}\thttps://example.test/registry\t"
                        f"{sha256(data).hexdigest()}\t{len(data)}\tdownloaded")
        catalog = json.loads((SCRIPTS.parent / "data/v41-upstream-sources.json").read_text())
        sources = tuple(sorted(name for group in catalog for name in group["files"])) + ("telegram-official-cidrs.txt",)
        for member in sources:
            data = member.encode("ascii")
            (self.candidate / member).write_bytes(data)
            rows.append(f"source\t{member}\thttps://example.test/source\t"
                        f"{sha256(data).hexdigest()}\t{len(data)}\tdownloaded")
        for member in BLOCK_MEMBERS:
            data = member.encode("ascii")
            (self.candidate / member).write_bytes(data)
            rows.append(f"block\t{member}\thttps://example.test/block\t"
                        f"{sha256(data).hexdigest()}\t{len(data)}\tdownloaded")
        path = self.candidate / provenance
        path.write_text("\n".join(rows) + "\n")
        result = create(path, self.candidate, self.candidate / bundle)
        (self.candidate / checksum).write_text(f"{result['bundle_sha256']}  {bundle}\n")
        self.env.update(INPUT_PROVENANCE=provenance, REGISTRY_INPUTS_ARCHIVE=bundle,
                        REGISTRY_INPUTS_SHA=checksum)
        upstream, upstream_sha = "v41-upstream-inputs.tar.gz", "geoip_RU_v41_upstream_inputs.sha256sum"
        result = create(path, self.candidate, self.candidate / upstream, members=sources)
        (self.candidate / upstream_sha).write_text(f"{result['bundle_sha256']}  {upstream}\n")
        self.env.update(UPSTREAM_INPUTS_ARCHIVE=upstream, UPSTREAM_INPUTS_SHA=upstream_sha)
        block, block_sha = "v41-block-inputs.tar.gz", "geoip_RU_v41_block_inputs.sha256sum"
        result = create(path, self.candidate, self.candidate / block, members=BLOCK_MEMBERS)
        (self.candidate / block_sha).write_text(f"{result['bundle_sha256']}  {block}\n")
        self.env.update(BLOCK_INPUTS_ARCHIVE=block, BLOCK_INPUTS_SHA=block_sha, RELEASE_MANIFEST=MANIFEST)
        # Preserve production asset names for the staged release and the fake public store.
        test_files = {
            "V41_OUTPUT_FILE":"geoip_RU.dat", "OUTPUT_SHA_FILE":"geoip_RU.dat.sha256sum",
            "V41_QUALITY_REPORT":"geoip_RU_quality_report.txt", "V41_MANIFEST":"geoip_RU_v41_manifest.json",
        }
        if provenance == "geoip_RU_input_provenance.tsv":
            self.env.update(test_files)
        for name in CORE[::2]:
            data = name.encode("ascii")
            (self.candidate / name).write_bytes(data)
            (self.candidate / (name + ".sha256sum")).write_text(f"{sha256(data).hexdigest()}  {name}\n")
        (self.candidate / "geoip_RU_quality_report.txt").write_text("report")
        (self.candidate / "geoip_RU_v41_manifest.json").write_text(json.dumps({
            "output_sha256": sha256((self.candidate / "geoip_RU.dat").read_bytes()).hexdigest(),
            "input_provenance_sha256": sha256(path.read_bytes()).hexdigest(),
        }))
        (self.candidate / "geoip_RU_input_provenance.tsv").write_bytes(path.read_bytes())
        self.refresh_manifest()

    def refresh_manifest(self):
        (self.candidate / MANIFEST).write_text(json.dumps(make(
            self.candidate, "a"*40, self.repo, "123", "1")))

    def provide_upstream_asset(self):
        (self.root / "published-upstream").write_bytes(
            (self.candidate / "v41-upstream-inputs.tar.gz").read_bytes())
        public = self.root / "public-snapshot"
        public.mkdir(exist_ok=True)
        for name in (*SNAPSHOT, MANIFEST):
            (public / name).write_bytes((self.candidate / name).read_bytes())

    def provide_registry_asset(self):
        self.provide_upstream_asset()
        self.registry_asset.write_bytes((self.candidate / self.env["REGISTRY_INPUTS_ARCHIVE"]).read_bytes())

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
        gh.write_text('#!/bin/sh\ncp as-ip-blocks.tar.gz "$TEST_ASSET"\n'
                      'cp v41-registry-inputs.tar.gz "$TEST_REGISTRY_ASSET"\n')
        gh.chmod(0o700)
        upload = self.invoke("publish_v41_snapshot_release.sh")
        self.assertEqual(upload.returncode, 0, upload.stderr)
        self.assertEqual(self.asset.read_bytes(), archive)
        self.provide_upstream_asset()
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
        self.provide_registry_asset()
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
        self.provide_registry_asset()
        result = self.invoke("promote_v41_release.sh", TEST_REMOTE=str(self.remote), COMPETING_SHA=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale info", result.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), other)

    def test_registry_archive_must_be_public_and_match_the_tagged_checksum(self):
        self.setup_git()
        archive = self.prepare_retained_archive()
        start = self.env["PREVIOUS_RELEASE_SHA"]
        target = self.stage()
        self.asset.write_bytes(archive)
        missing = self.invoke("promote_v41_release.sh")
        self.assertEqual(missing.returncode, 22, missing.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        self.provide_registry_asset()
        raw = self.registry_asset.read_bytes()
        self.registry_asset.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        bad = self.invoke("promote_v41_release.sh")
        self.assertNotEqual(bad.returncode, 0)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        self.provide_registry_asset()
        ok = self.invoke("promote_v41_release.sh")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), target)

    def test_missing_public_block_bundle_and_wrong_srs_do_not_advance_release(self):
        self.setup_git()
        archive = self.prepare_retained_archive()
        start = self.env["PREVIOUS_RELEASE_SHA"]
        target = self.stage()
        self.asset.write_bytes(archive)
        self.provide_registry_asset()
        public = self.root / "public-snapshot"
        (public / "v41-block-inputs.tar.gz").unlink()
        missing = self.invoke("promote_v41_release.sh")
        self.assertEqual(missing.returncode, 22, missing.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        self.provide_registry_asset()
        path = public / "geoip_RU.srs"
        data = path.read_bytes()
        path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
        bad = self.invoke("promote_v41_release.sh")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("release asset mismatch: geoip_RU.srs", bad.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), start)
        self.provide_registry_asset()
        good = self.invoke("promote_v41_release.sh")
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), target)

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
        self.prepare_registry(env["INPUT_PROVENANCE"], archive_bytes)
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
        self.refresh_manifest()
        result = self.invoke("publish_v41_snapshot_release.sh", **env)
        self.assertNotEqual(result.returncode, 0)
        command, = [json.loads(row) for row in capture.read_text().splitlines()]
        self.assertEqual(command[:3], ["release", "create", "v41.3"])
        self.assertIn("as-ip-blocks.tar.gz", command)
        self.assertIn("v41-registry-inputs.tar.gz", command)
        self.assertIn("v41-upstream-inputs.tar.gz", command)
        self.assertIn("v41-block-inputs.tar.gz", command)
        self.assertIn(MANIFEST, command)
        self.assertIn("geoip_RU.dat", command)
        self.assertIn("geoip_RU.srs", command)
        self.assertIn("geoip_PRIVATE.srs", command)
        self.assertIn("--verify-tag", command)
        self.assertIn("--latest=false", command)

    def test_rolling_readback_fails_for_stale_assets(self):
        self.setup_git()
        archive = self.prepare_retained_archive()
        target = self.stage()
        self.asset.write_bytes(archive)
        self.provide_registry_asset()
        ok = self.invoke("promote_v41_release.sh")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        published = self.root / "public-snapshot"
        raw = self.root / "public-raw"
        raw.mkdir()
        for n in (*CORE, MANIFEST):
            (raw / n).write_bytes((published / n).read_bytes())
        (self.root / "sleep").write_text("#!/bin/sh\nexit 0\n")
        (self.root / "sleep").chmod(0o700)
        curl = self.root / "curl"
        curl.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, shutil, sys\n"
            "url = sys.argv[-1]\n"
            "root = os.environ['TEST_RAW' if 'raw.githubusercontent.com' in url else 'TEST_PUBLIC']\n"
            "shutil.copyfile(pathlib.Path(root) / url.rsplit('/',1)[1], sys.argv[sys.argv.index('--output')+1])\n"
        )
        curl.chmod(0o700)
        ok = self.invoke("verify_v41_rolling_release.sh", TEST_RAW=str(raw))
        self.assertEqual(ok.returncode, 0, ok.stderr + ok.stdout)
        (published / "geoip_RU.dat").write_bytes(b"old")
        bad = self.invoke("verify_v41_rolling_release.sh", TEST_RAW=str(raw))
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("partial publication", bad.stdout)
        self.assertEqual(self.git("rev-parse", "release", cwd=self.remote), target)



if __name__ == "__main__":
    unittest.main()
