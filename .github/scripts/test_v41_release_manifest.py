import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bundle_v41_registry_inputs import BLOCK_MEMBERS, create, restore
from v41_release_manifest import CORE, PRIVATE_MRS, SCHEMA, SNAPSHOT, describe, make, verify


class ReleaseManifestTests(unittest.TestCase):
    def test_release_identity_and_exact_binary_and_checksum_comparison(self):
        with TemporaryDirectory() as directory:
            p = Path(directory)
            for name in SNAPSHOT:
                (p / name).write_text(name)
            for name in CORE[::2]:
                h = describe(p / name)["sha256"]
                (p / (name + ".sha256sum")).write_text(f"{h}  {name}\n")
            policy = p / "geoip_RU_v41_manifest.json"
            policy.write_text(json.dumps({
                "output_sha256": describe(p / "geoip_RU.dat")["sha256"],
                "input_provenance_sha256": describe(p / "geoip_RU_input_provenance.tsv")["sha256"],
            }))
            data = make(p, "a"*40, "example/geoip", "123", "1")
            self.assertEqual(data["schema"], SCHEMA)
            self.assertIn("geoip_RU.mrs", data["assets"])
            self.assertIn("geoip_RU.mrs.sha256sum", data["assets"])
            self.assertEqual(data["source_commit"], "a"*40)
            self.assertEqual(data["workflow_run"], "https://github.com/example/geoip/actions/runs/123")
            manifest = p / "manifest.json"
            manifest.write_text(json.dumps(data))
            verify(p, manifest, SNAPSHOT)
            for name in PRIVATE_MRS:
                with self.subTest(name=name):
                    (p / name).touch()
                    with self.assertRaisesRegex(ValueError, "Forbidden v41 artifact"):
                        make(p, "a"*40, "example/geoip", "123", "1")
                    with self.assertRaisesRegex(ValueError, "Forbidden v41 artifact"):
                        verify(p, manifest, CORE)
                    (p / name).unlink()
            check = p / "geoip_PRIVATE.srs.sha256sum"
            check.write_text(check.read_text().replace("  ", " *"))
            with self.assertRaisesRegex(ValueError, "release asset mismatch: geoip_PRIVATE.srs.sha256sum"):
                verify(p, manifest, CORE)
            with self.assertRaisesRegex(ValueError, "checksum sidecar does not match geoip_PRIVATE.srs"):
                make(p, "a"*40, "example/geoip", "123", "1")

    def test_block_bundle_archives_exact_optional_fallback(self):
        with TemporaryDirectory() as directory:
            p = Path(directory)
            rows = ["SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS"]
            missing = "antifilter-ipresolve.lst"
            url = "https://example.test/ipresolve"
            for member in BLOCK_MEMBERS:
                source = p / member
                if member == missing:
                    source.write_text(f"# Optional source unavailable during this build: {url}\n")
                    rows.append(f"example\t{member}\t{url}\t-\t0\tunavailable")
                else:
                    source.write_text(member)
                    h = describe(source)
                    rows.append(f"example\t{member}\t{url}\t{h['sha256']}\t{h['bytes']}\tdownloaded")
            provenance = p / "provenance.tsv"
            provenance.write_text("\n".join(rows) + "\n")
            bundle = p / "bundle.tar.gz"
            data = create(provenance, p, bundle, members=BLOCK_MEMBERS)
            self.assertEqual(data["files"][missing]["status"], "unavailable")
            d = p / "restored"
            restore(provenance, bundle, d, members=BLOCK_MEMBERS)
            self.assertEqual((d / missing).read_bytes(), (p / missing).read_bytes())
            (p / missing).write_text("different bytes")
            with self.assertRaisesRegex(ValueError, "original registry input mismatch"):
                create(provenance, p, p / "second.tar.gz", members=BLOCK_MEMBERS)


if __name__ == "__main__":
    unittest.main()
