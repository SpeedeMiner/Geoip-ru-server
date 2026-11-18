import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bundle_v41_registry_inputs import BLOCK_MEMBERS, HEADER, MEMBERS, create
from v41_release_manifest import CORE, LEGACY_CORE, LEGACY_SNAPSHOT, MANIFEST, MAX_BYTES, SCHEMA, SNAPSHOT
from verify_v41_snapshot_replay import (
    BUNDLES, CATALOG, INPUTS, IPVERSE, PROVENANCE, TELEGRAM, catalog_members,
    compare_client_files, load_manifest, read_historical_catalog, restore_inputs,
)


def describe(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


class SnapshotReplayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.output = self.root / "output"
        self.manifest = self.inputs / MANIFEST
        self.checkout = self.root / "source"
        self.commit = "1" * 40
        self.upstream_names = ("feed.dat", TELEGRAM)
        self.catalog = b'[{"files":{"feed.dat":"release/sample.dat"}}]'
        self.assets = {name: describe(b"unused") for name in SNAPSHOT}
        for name in CORE[::2]:
            raw = f"binary fixture for {name}".encode()
            self.put_asset(self.candidate, name, raw)
            digest = self.assets[name]["sha256"]
            self.put_asset(self.candidate, name + ".sha256sum", f"{digest}  {name}\n".encode())

    def put_asset(self, directory, name, raw):
        (directory / name).write_bytes(raw)
        self.assets[name] = describe(raw)

    def write_manifest(self, **changes):
        doc = {"schema": SCHEMA, "source_commit": self.commit, "assets": self.assets, **changes}
        raw = json.dumps(doc).encode()
        self.manifest.write_bytes(raw)
        return describe(raw)["sha256"]

    def prepare_bundle_fixture(self):
        self.checkout.mkdir()
        staged = self.root / "original-inputs"
        staged.mkdir()
        rows = ["\t".join(HEADER)]
        ipverse = gzip.compress(b"fixture" + b"x" * 5_000_000, compresslevel=0, mtime=0)
        self.put_asset(self.inputs, IPVERSE, ipverse)
        members = (MEMBERS, self.upstream_names, BLOCK_MEMBERS)
        for name in (IPVERSE, *(n for group in members for n in group)):
            if name == IPVERSE:
                raw = ipverse
            else:
                raw = f"fixture for {name}\n".encode()
                (staged / name).write_bytes(raw)
            spec = describe(raw)
            rows.append(f"fixture\t{name}\thttps://example.invalid/a\t{spec['sha256']}\t{spec['bytes']}\tdownloaded")
        self.put_asset(self.inputs, PROVENANCE, ("\n".join(rows) + "\n").encode())
        for name, group in zip(BUNDLES, members):
            path = self.inputs / name
            create(self.inputs / PROVENANCE, staged, path, members=group)
            self.assets[name] = describe(path.read_bytes())
        return staged

    def test_manifest_requires_independent_digest(self):
        digest = self.write_manifest()
        self.assertEqual(load_manifest(self.manifest, digest)["source_commit"], self.commit)
        self.manifest.write_bytes(self.manifest.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            load_manifest(self.manifest, digest)

    def test_manifest_rejects_duplicates_even_if_digest_matches(self):
        self.write_manifest()
        raw = self.manifest.read_bytes().replace(b'"schema": 2', b'"schema": 1, "schema": 2')
        self.manifest.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            load_manifest(self.manifest, describe(raw)["sha256"])

    def test_manifest_rejects_invalid_schema_and_sizes(self):
        for schema in (True, 3, None):
            with self.subTest(schema=schema), self.assertRaisesRegex(ValueError, "schema"):
                load_manifest(self.manifest, self.write_manifest(schema=schema))
        self.assets[IPVERSE]["bytes"] = True
        with self.assertRaisesRegex(ValueError, "manifest identity"):
            load_manifest(self.manifest, self.write_manifest())

    def test_legacy_snapshots_still_compare_only_the_legacy_inventory(self):
        legacy = {name: self.assets[name] for name in LEGACY_SNAPSHOT}
        manifest = load_manifest(self.manifest, self.write_manifest(schema=1, assets=legacy))
        report = compare_client_files(manifest, self.candidate)
        self.assertEqual(set(report), set(LEGACY_CORE))
        self.assertTrue(all(row["match"] for row in report.values()))
        with self.assertRaisesRegex(ValueError, "inventory"):
            load_manifest(self.manifest, self.write_manifest(schema=1))

    def test_schema_two_requires_both_ru_mrs_files_and_refuses_private(self):
        for name in ("geoip_RU.mrs", "geoip_RU.mrs.sha256sum"):
            with self.subTest(name=name):
                assets = {k: v for k, v in self.assets.items() if k != name}
                with self.assertRaisesRegex(ValueError, "inventory"):
                    load_manifest(self.manifest, self.write_manifest(assets=assets))
        manifest = load_manifest(self.manifest, self.write_manifest())
        (self.candidate / "geoip_RU.mrs").write_bytes(b"stale")
        self.assertFalse(compare_client_files(manifest, self.candidate)["geoip_RU.mrs"]["match"])
        (self.candidate / "geoip_PRIVATE.mrs").touch()
        with self.assertRaisesRegex(ValueError, "Forbidden v41 artifact"):
            compare_client_files(manifest, self.candidate)

    def test_manifest_rejects_extra_asset_and_unbound_sidecar(self):
        self.assets["../oops"] = describe(b"data")
        with self.assertRaisesRegex(ValueError, "inventory"):
            load_manifest(self.manifest, self.write_manifest())
        del self.assets["../oops"]
        self.assets["geoip_RU.dat.sha256sum"] = describe(b"some other sidecar")
        with self.assertRaisesRegex(ValueError, "sidecar does not bind"):
            load_manifest(self.manifest, self.write_manifest())

    def test_compare_reports_matches_and_distinguishes_absent_and_changed_files(self):
        manifest = load_manifest(self.manifest, self.write_manifest())
        self.assertTrue(all(x["match"] for x in compare_client_files(manifest, self.candidate).values()))
        data = self.candidate / "geoip_RU.dat"
        data.write_bytes(b"X" * data.stat().st_size)
        (self.candidate / "geoip_RU.srs").unlink()
        report = compare_client_files(manifest, self.candidate)
        self.assertNotEqual(report[data.name]["actual"], report[data.name]["expected"])
        self.assertFalse(report[data.name]["match"])
        self.assertIn("error", report["geoip_RU.srs"])
        self.assertTrue(report["geoip_PRIVATE.srs"]["match"])

    def test_compare_refuses_fifo_symlink_and_oversized_file(self):
        manifest = load_manifest(self.manifest, self.write_manifest())
        names = CORE[::2]
        for name in names:
            (self.candidate / name).unlink()
        (self.candidate / names[0]).symlink_to(self.manifest)
        os.mkfifo(self.candidate / names[1])
        with (self.candidate / names[2]).open("wb") as f:
            f.truncate(MAX_BYTES + 1)
        report = compare_client_files(manifest, self.candidate)
        self.assertFalse(any(report[name]["match"] for name in names))
        self.assertIn("not a regular file", report[names[1]]["error"])
        self.assertIn("exceeds its bound", report[names[2]]["error"])

    def test_catalog_rejects_path_fields_reserved_and_duplicate_names(self):
        for raw in (
            b'[{"files":{"../escape":"x"}}]',
            b'[{"files":{"geoip_RU.dat":"x"}}]',
            b'[{"files":{"telegram-official-cidrs.txt":"x"}}]',
            b'[{"files":{"same":"x"}},{"files":{"same":"y"}}]',
            b'[{"files":{"same":"x","same":"y"}}]',
            b'{"files":{"sample":"x"}}',
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                catalog_members(raw)
        self.assertEqual(catalog_members(self.catalog), self.upstream_names)

    @patch("verify_v41_snapshot_replay.read_historical_catalog")
    def test_restores_only_build_inputs_both_archive_and_partial_packages(self, catalog):
        staged = self.prepare_bundle_fixture()
        catalog.return_value = self.catalog
        manifest = load_manifest(self.manifest, self.write_manifest())
        # A neighboring build output is ignored, never used as input.
        (self.inputs / "geoip_RU.dat").write_bytes(b"not used")
        with patch("sys.stderr", new=io.StringIO()):
            names = restore_inputs(manifest, self.inputs, self.checkout, self.output)
        expected = {p.name: p.read_bytes() for p in staged.iterdir()}
        expected.update({name: (self.inputs / name).read_bytes() for name in INPUTS[:2]})
        self.assertEqual(set(names), expected.keys())
        self.assertEqual({p.name: p.read_bytes() for p in self.output.iterdir()}, expected)
        catalog.assert_called_once_with(self.checkout, self.commit)

    @patch("verify_v41_snapshot_replay.read_historical_catalog")
    def test_tamper_at_manifest_and_embedded_archive_layers_leaves_no_output(self, catalog):
        self.prepare_bundle_fixture()
        catalog.return_value = self.catalog
        manifest = load_manifest(self.manifest, self.write_manifest())
        block = self.inputs / BUNDLES[-1]
        raw = block.read_bytes()
        block.write_bytes(b"X" + raw[1:])
        with self.assertRaisesRegex(ValueError, "release input mismatch"), patch("sys.stderr", new=io.StringIO()):
            restore_inputs(manifest, self.inputs, self.checkout, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".v41-restore-*")))
        expanded = gzip.decompress(raw)
        name = BLOCK_MEMBERS[0]
        old = f"fixture for {name}\n".encode()
        modified = expanded.replace(old, b"X" + old[1:], 1)
        self.assertNotEqual(expanded, modified)
        block.write_bytes(gzip.compress(modified, mtime=0))
        self.assets[block.name] = describe(block.read_bytes())
        manifest = load_manifest(self.manifest, self.write_manifest())
        with self.assertRaisesRegex(ValueError, "archive member digest mismatch"), patch("sys.stderr", new=io.StringIO()):
            restore_inputs(manifest, self.inputs, self.checkout, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".v41-restore-*")))

    def test_preexisting_and_input_nested_output_refused(self):
        self.checkout.mkdir()
        manifest = load_manifest(self.manifest, self.write_manifest())
        self.output.mkdir()
        marker = self.output / "marker"
        marker.write_text("keep")
        with self.assertRaises(FileExistsError):
            restore_inputs(manifest, self.inputs, self.checkout, self.output)
        self.assertEqual(marker.read_text(), "keep")
        for parent in (self.inputs, self.checkout):
            with self.subTest(parent=parent), self.assertRaisesRegex(ValueError, "output must be outside"):
                restore_inputs(manifest, self.inputs, self.checkout, parent / "output")

    @patch("verify_v41_snapshot_replay.read_historical_catalog")
    def test_collisions_between_archives_refused_before_extraction(self, catalog):
        self.checkout.mkdir()
        catalog.return_value = json.dumps([{"files": {MEMBERS[0]: "old/asset"}}]).encode()
        manifest = load_manifest(self.manifest, self.write_manifest())
        with self.assertRaisesRegex(ValueError, "collide"):
            restore_inputs(manifest, self.inputs, self.checkout, self.output)
        self.assertFalse(self.output.exists())

    def test_historical_catalog_ignores_worktree_and_replace_ref(self):
        env = dict(os.environ, GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                   GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
        self.checkout.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(self.checkout), *args], check=True,
                                  capture_output=True, env=env).stdout.strip().decode()
        git("init", "-q")
        catalog = self.checkout / CATALOG
        catalog.parent.mkdir(parents=True)
        catalog.write_bytes(self.catalog)
        git("add", CATALOG)
        git("-c", "commit.gpgsign=false", "commit", "-qm", "historical")
        original = git("rev-parse", "HEAD")
        catalog.write_text("other")
        git("add", CATALOG)
        git("-c", "commit.gpgsign=false", "commit", "-qm", "replacement")
        git("replace", original, git("rev-parse", "HEAD"))
        catalog.write_text("untracked edit")
        self.assertEqual(read_historical_catalog(self.checkout, original), self.catalog)
        with self.assertRaisesRegex(ValueError, "unavailable locally"):
            read_historical_catalog(self.checkout, "f" * 40)

    def test_compare_cli_json_and_exit_codes(self):
        command = [sys.executable, str(Path(__file__).with_name("verify_v41_snapshot_replay.py")),
                   "--manifest", str(self.manifest), "--manifest-sha256", self.write_manifest(),
                   "compare-client", "--replay", str(self.candidate)]
        for status in (0, 1, 2):
            result = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, status)
            if status < 2:
                self.assertEqual(json.loads(result.stdout)["ok"], status == 0)
            else:
                self.assertFalse(result.stdout)
            if status == 0:
                (self.candidate / CORE[0]).unlink()
            elif status == 1:
                self.manifest.write_bytes(b"wrong")


if __name__ == "__main__":
    unittest.main()
