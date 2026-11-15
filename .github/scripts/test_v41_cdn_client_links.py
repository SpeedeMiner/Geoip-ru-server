import subprocess
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

import audit_v41_cdn_public as audit

BASE = Path(__file__).resolve().parents[2]
REPO = "SpeedeMiner/Geoip-ru-server"
PREFIX = f"https://cdn.jsdelivr.net/gh/{REPO}"
NOTES = BASE / "docs/V41_ROLLING_RELEASE_NOTES.md"


class ReleaseNotesTests(unittest.TestCase):
    def test_release_links_are_exactly_the_three_client_files(self):
        audit.validate_release_links(NOTES.read_text(), REPO)

    def test_another_repos_upstream_url_is_not_a_client_link(self):
        audit.validate_release_links(
            NOTES.read_text() + "\nhttps://cdn.jsdelivr.net/gh/upstream/geoip@release/source.dat",
            REPO,
        )

    def test_legacy_or_service_artifact_link_is_rejected(self):
        notes = NOTES.read_text()
        for extra in (
            f"{PREFIX}@release/geoip_RU.dat",
            f"{PREFIX}@cdn/hydra-geoip.dat",
            f"{PREFIX}@cdn/geoip_RU.dat.sha256sum",
            f"{PREFIX}@main/docs/V41_CDN_PUBLICATION_JOURNAL_20261115.md",
            f"{PREFIX}@cdn/geoip_RU.srs",  # Do not print duplicate client links.
            f"https://fastly.jsdelivr.net/gh/{REPO}@release/audit.tsv",
        ):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "client links"):
                audit.validate_release_links(notes + "\n" + extra, REPO)


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow log check")
class PublicationLogTests(unittest.TestCase):
    def test_links_hidden_until_public_readback_is_verified(self):
        workflow = yaml.safe_load((BASE / ".github/workflows/geoip-v41.yml").read_bytes())
        steps = workflow["jobs"]["publish"]["steps"]
        log = next(s["run"] for s in steps if s["name"] == "Print download and audit URLs")
        snapshot = "geoip-v41-snapshot-12345.1"
        replacements = {
            "github.server_url": "https://github.com",
            "github.repository": REPO,
            "steps.cdn_ref.outputs.cdn_sha": "a" * 40,
            "steps.snapshot_ref.outputs.snapshot": snapshot,
            "steps.snapshot_ref.outputs.snapshot_sha": "b" * 40,
        }
        def render(status):
            result = log
            for key, value in {**replacements, "steps.cdn_ref.outputs.cdn_status": status}.items():
                result = result.replace("${{ " + key + " }}", value)
            return subprocess.run(["bash", "-e", "-s"], input=result, text=True,
                                  capture_output=True, check=True).stdout

        for status in ("verified", "origin_unconfirmed", "public_unconfirmed", ""):
            with self.subTest(status=status):
                output = render(status)
                self.assertIn(f"https://github.com/{REPO}/releases/tag/{snapshot}", output)
                self.assertIn(f"Release commit: {'b' * 40}", output)
                if status == "verified":
                    audit.validate_release_links(output, REPO)
                else:
                    self.assertNotIn("cdn.jsdelivr.net", output)
                    self.assertIn("Use the versioned GitHub snapshot", output)


if __name__ == "__main__":
    unittest.main()
