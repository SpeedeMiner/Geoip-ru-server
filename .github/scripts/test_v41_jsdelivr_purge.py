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
assert key.startswith("/gh/SpeedeMiner/Geoip-ru-server@cdn/")
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
        "/gh/unrelated/repo@cdn/other.dat": {
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
            self.assertEqual(seen, ["geoip_RU.dat", "geoip_RU.srs", "geoip_PRIVATE.srs"])
            return result, summary.read_text()

    def test_accepts_only_confirmed_success_for_each_requested_path(self):
        result, summary = self.run_script({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Confirmed: 3/3. Failed: 0.", summary)
        self.assertNotIn("Unconfirmed:", summary)

    def test_attempts_every_path_even_after_transport_and_api_errors(self):
        for failure in ("transport", "invalid", "wrong-path", "provider-failure",
                        "throttled", "pending", "empty-providers"):
            with self.subTest(failure=failure):
                result, summary = self.run_script({"geoip_RU.dat": failure})
                self.assertEqual(result.returncode, 1)
                self.assertIn("Confirmed: 2/3. Failed: 1.", summary)
                self.assertIn("run-specific GitHub Release", summary)
                self.assertIn("Unconfirmed: geoip_RU.dat", summary)


if __name__ == "__main__":
    unittest.main()
