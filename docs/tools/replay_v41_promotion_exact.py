"""Exercise v41 promotion with the real PR #32 candidate but only local Git writes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from replay_v41_combined import EXPECTED_ZIP, digest

ROOT = Path.cwd()
CANDIDATE = ROOT / "candidate-14116411312.zip"
TREE = ROOT / "combined-tree"
TAG = "geoip-v41-snapshot-43600293291.1"
ARCHIVE = "as-ip-blocks.tar.gz"


def run():
    if digest(CANDIDATE) != EXPECTED_ZIP:
        raise ValueError("invalid candidate archive")
    with tempfile.TemporaryDirectory() as work:
        root = Path(work)
        remote, seed, candidate, binaries = [root / n for n in ("remote", "seed", "candidate", "bin")]
        candidate.mkdir()
        binaries.mkdir()
        with zipfile.ZipFile(CANDIDATE) as z:
            for name in z.namelist():
                if Path(name).name != name:
                    raise ValueError(name)
                with z.open(name) as src, (candidate / name).open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        env = {**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{remote.as_uri()}.insteadOf",
               "GIT_CONFIG_VALUE_0": "https://github.com/example/geoip.git", "GITHUB_REPOSITORY": "example/geoip",
               "GITHUB_TOKEN": "local-test-only", "GITHUB_RUN_ID": "43600293291", "GITHUB_RUN_ATTEMPT": "1",
               "GITHUB_EVENT_NAME": "workflow_dispatch", "SNAPSHOT_VERSION": "", "GITHUB_OUTPUT": str(root / "outputs"),
               "GH_TOKEN": "local-test-only", "PATH": f"{binaries}:{os.environ['PATH']}", "MOCK_PUBLIC": str(root / "public")}
        def git(*args, cwd=root):
            return subprocess.check_output(["git", *args], cwd=cwd, env=env, stderr=subprocess.PIPE, text=True).strip()
        git("init", "--bare", str(remote))
        git("init", "-b", "release", str(seed))
        shutil.copyfile(ROOT / "public-downloads/rolling-geoip_RU.dat", seed / "geoip_RU.dat")
        git("add", "geoip_RU.dat", cwd=seed)
        git("-c", "user.name=Replay", "-c", "user.email=replay@example.invalid", "commit", "-m", "Fixture release", cwd=seed)
        git("push", str(remote), "release", cwd=seed)
        start = git("rev-parse", "release", cwd=remote)
        import yaml
        wf = yaml.load((TREE / ".github/workflows/geoip-v41.yml").read_text(), Loader=yaml.BaseLoader)
        env.update(wf["env"], PREVIOUS_RELEASE_SHA=start)
        # Guard all GitHub CLI and public download calls with local-only shims.
        gh = binaries / "gh"
        gh.write_text("#!/usr/bin/env python3\nimport os,pathlib,shutil,sys\n"
                      "assert sys.argv[1:4] == ['release','create',os.environ['SNAPSHOT_TAG']]\n"
                      "assert '--verify-tag' in sys.argv and '--latest=false' in sys.argv\n"
                      "if os.environ.get('SIMULATE_FAILED_UPLOAD'): sys.exit(1)\n"
                      "assert 'as-ip-blocks.tar.gz' in sys.argv\n"
                      "shutil.copyfile('as-ip-blocks.tar.gz', os.environ['MOCK_PUBLIC'])\n")
        gh.chmod(0o700)
        curl = binaries / "curl"
        curl.write_text("#!/usr/bin/env python3\nimport os,pathlib,shutil,sys\n"
                        "assert sys.argv[-1].endswith('/'+os.environ['SNAPSHOT_TAG']+'/as-ip-blocks.tar.gz')\n"
                        "p=pathlib.Path(os.environ['MOCK_PUBLIC'])\n"
                        "if not p.exists(): sys.exit(22)\n"
                        "shutil.copyfile(p,sys.argv[sys.argv.index('--output')+1])\n")
        curl.chmod(0o700)
        def invoke(name, **overrides):
            return subprocess.run(["bash", str(TREE / ".github/scripts" / name)], cwd=candidate,
                                  env={**env, **overrides}, capture_output=True, text=True)
        stage = invoke("publish_v41_git_refs.sh")
        assert stage.returncode == 0, stage.stderr
        values = dict(line.split("=", 1) for line in Path(env["GITHUB_OUTPUT"]).read_text().splitlines())
        assert values["snapshot"] == TAG
        env.update(SNAPSHOT_TAG=TAG, SNAPSHOT_SHA=values["snapshot_sha"])
        assert git("rev-parse", "release", cwd=remote) == start
        upload_fail = invoke("publish_v41_snapshot_release.sh", SIMULATE_FAILED_UPLOAD="1")
        assert upload_fail.returncode == 1, upload_fail.stderr
        missing = invoke("promote_v41_release.sh")
        assert missing.returncode == 22, missing.stderr
        assert git("rev-parse", "release", cwd=remote) == start
        upload = invoke("publish_v41_snapshot_release.sh")
        assert upload.returncode == 0, upload.stderr
        assert git("rev-parse", "release", cwd=remote) == start
        promote = invoke("promote_v41_release.sh")
        assert promote.returncode == 0, promote.stderr
        assert git("rev-parse", "release", cwd=remote) == values["snapshot_sha"]
        assert git("rev-parse", "release^", cwd=remote) == start
        assert git("rev-parse", TAG, cwd=remote) == values["snapshot_sha"]
        return {"archive_sha256": digest(candidate / ARCHIVE), "archive_bytes": (candidate / ARCHIVE).stat().st_size,
                "upload_failure_keeps_old_release": True, "missing_public_archive_keeps_old_release": True,
                "success_advances_release_exactly_to_verified_tagged_child": True,
                "git": "local bare repo", "gh_and_curl": "local fixtures", "external_writes": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
