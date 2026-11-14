import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().with_name("purge_v41_jsdelivr.sh")
FAKE_CURL = '''import json, os, sys
from pathlib import Path
from urllib.parse import urlparse

url = urlparse(sys.argv[-1])
assert url.scheme == "https" and url.netloc == "purge.jsdelivr.net"
key = url.path
assert key.startswith("/gh/SpeedeMiner/Geoip-ru-server@release/")
name = key.rsplit("/", 1)[1]
with Path(os.environ["TEST_CALLS"]).open("a") as log:
    log.write(name + "\\n")
case = json.loads(os.environ["TEST_SCENARIOS"]).get(name)
if case == "transport":
    sys.exit(28)
if case == "invalid":
    print("<html>Not JSON")
    sys.exit(0)
result = {
    "status": "pending" if case == "pending" else "finished",
    "paths": {
        "/gh/unrelated/repo@release/other.dat": {
            "throttled": False, "providers": {"CF": True, "FY": True},
        },
    },
}
if case != "wrong-path":
    result["paths"][key] = {
        "throttled": case == "throttled",
        "providers": {} if case == "empty-providers" else {"CF": True, "FY": case != "provider-failure"},
    }
print(json.dumps(result))
'''


class JsdelivrPurgeTests(unittest.TestCase):
    def run_script(self, failure_cases):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            mock = base / "curl"
            mock.write_text(f"#!{sys.executable}\n" + FAKE_CURL)
            mock.chmod(0o755)
            summary, calls = base / "summary", base / "calls"
            env = dict(os.environ, PATH=f"{base}{os.pathsep}{os.environ['PATH']}",
                       GITHUB_REPOSITORY="SpeedeMiner/Geoip-ru-server",
                       GITHUB_STEP_SUMMARY=str(summary), TEST_CALLS=str(calls),
                       TEST_SCENARIOS=json.dumps(failure_cases))
            result = subprocess.run(["bash", str(SCRIPT)], env=env, text=True, capture_output=True, check=False)
            seen = calls.read_text().splitlines()
            self.assertEqual(len(set(seen)), len(seen))
            self.assertEqual(len(seen), 22)
            self.assertEqual(seen[0], "geoip_RU.dat")
            self.assertEqual(seen[-1], "geoip_RU_blocked_ip_exclusions.txt")
            return result, summary.read_text()

    def test_accepts_only_confirmed_success_for_each_requested_path(self):
        result, summary = self.run_script({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Confirmed: 22/22. Failed: 0.", summary)
        self.assertNotIn("Unconfirmed:", summary)

    def test_attempts_every_path_even_after_transport_and_api_errors(self):
        failure_cases = {
            "geoip_RU.dat": "transport",
            "geoip_RU.dat.sha256sum": "invalid",
            "geoip_RU.srs": "wrong-path",
            "geoip_RU.srs.sha256sum": "provider-failure",
            "geoip_PRIVATE.srs": "throttled",
            "geoip_PRIVATE.srs.sha256sum": "pending",
            "geoip_RU_quality_report.txt": "empty-providers",
        }
        result, summary = self.run_script(failure_cases)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Confirmed: 15/22. Failed: 7.", summary)
        self.assertIn("run-specific GitHub Release", summary)
        for name in failure_cases:
            self.assertIn(f"Unconfirmed: {name}", summary)


if __name__ == "__main__":
    unittest.main()
