from __future__ import annotations

import json
import unittest

from read_v41_release_state import (ARCHIVE, BLOCK_CHECKSUM, DAT, DAT_CHECKSUM,
    MANIFEST, MARKER, PROVENANCE, QUALITY, ROLLING, digest, readback)

TIP, TARGET, STALE = ("a" * 40, "b" * 40, "c" * 40)
TAG = "geoip-v41-snapshot-1234.1"


class Fixture:
    def __init__(self):
        self.release_tip = TIP
        self.tagged = TARGET
        self.parents_of = {TARGET: [TIP]}
        self.files = {}
        self.releases = {}
        self.downloads = {}
        self.archive = b"a" * 5_000_000
        self.put_tree(TIP, b"first", marker=None, generation="old")
        # Keep DAT exactly equal to ensure the test also detects stale sidecars.
        self.put_tree(TARGET, b"first", marker=TAG, generation="new")
        self.releases[ROLLING] = self.assets(TIP, ROLLING)

    def put_tree(self, sha, data, marker, generation):
        dat = digest(data)
        archive = digest(self.archive)
        self.files[sha] = {
            DAT: data,
            DAT_CHECKSUM: f"{dat['sha256']}  {DAT}\n".encode(),
            MANIFEST: json.dumps({"output_bytes": len(data), "output_sha256": dat["sha256"],
                                  "generated_at": generation}).encode(),
            QUALITY: f"quality {generation}\n".encode(),
            PROVENANCE: ("SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"
                         f"ipverse\t{ARCHIVE}\thttps://example.test/source\t"
                         f"{archive['sha256']}\t{archive['size']}\tdownloaded\n").encode(),
            BLOCK_CHECKSUM: b"mask fixture\n",
            MARKER: f"{marker}\n".encode() if marker else None,
        }

    def assets(self, sha, tag, retained=False):
        selected = {name: self.files[sha][name] for name in (DAT, DAT_CHECKSUM, MANIFEST, QUALITY)}
        if tag == ROLLING:
            for name in (BLOCK_CHECKSUM, PROVENANCE):
                selected[name] = self.files[sha][name]
        if retained:
            selected[ARCHIVE] = self.archive
        for name, data in selected.items():
            self.downloads[tag, name] = data
        return {"id": 1, "draft": False, "immutable": False, "assets": [
            {"name": name, "state": "uploaded", "size": len(data),
             "digest": "sha256:" + digest(data)["sha256"]} for name, data in selected.items()]}

    def tag(self, tag):
        return self.tagged

    def tip(self):
        return self.release_tip

    def parents(self, sha):
        return self.parents_of[sha]

    def raw_file(self, sha, name, optional=False):
        return self.files[sha][name]

    def release(self, tag):
        return self.releases.get(tag)

    def download(self, tag, name, size):
        if (tag, name) not in self.downloads:
            raise OSError("not publicly downloadable")
        return self.downloads[tag, name]


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.gh = Fixture()

    def read(self, verify=False):
        return readback(self.gh, TAG, verify)

    def test_tag_absent(self):
        self.gh.tagged = None
        self.assertEqual(self.read()["phase"], "no_snapshot_tag")

    def test_existing_legacy_snapshot_not_missing_retained_archive(self):
        self.gh.tagged = TIP
        self.gh.parents_of[TIP] = [STALE]
        self.gh.releases[TAG] = self.gh.assets(TIP, TAG)
        out = self.read(True)
        self.assertEqual(out["phase"], "legacy_snapshot")
        self.assertEqual(out["snapshot"]["downloads"][DAT], "verified")
        self.assertNotIn(ARCHIVE, out["snapshot"]["downloads"])

    def test_tag_only_and_draft_or_partial_are_not_ready(self):
        self.assertEqual(self.read()["snapshot"]["state"], "no_published_release")
        self.gh.releases[TAG] = {"id": 1, "draft": True}
        self.assertEqual(self.read()["snapshot"]["state"], "draft")
        self.gh.releases[TAG] = self.gh.assets(TARGET, TAG)
        self.assertEqual(self.read()["snapshot"]["assets"][ARCHIVE], "missing")
        self.assertEqual(self.read()["phase"], "staged_snapshot_not_public_or_incomplete")

    def test_complete_snapshot_and_later_promotion(self):
        self.gh.releases[TAG] = self.gh.assets(TARGET, TAG, True)
        out = self.read(True)
        self.assertEqual(out["snapshot"]["downloads"][ARCHIVE], "verified")
        self.assertEqual(out["phase"], "snapshot_verified_not_promoted")
        self.gh.release_tip = TARGET
        out = self.read()
        self.assertEqual(out["rolling"]["assets"][DAT], "metadata_match")
        self.assertEqual(out["rolling"]["assets"][MANIFEST], "digest_mismatch")
        self.assertEqual(out["phase"], "promoted_rolling_incomplete_or_stale")
        self.gh.releases[ROLLING] = self.gh.assets(TARGET, ROLLING)
        self.assertEqual(self.read(True)["phase"], "promoted_rolling_matches")

    def test_metadata_match_does_not_claim_bytes_have_been_read(self):
        self.gh.releases[TAG] = self.gh.assets(TARGET, TAG, True)
        meta = self.read()
        self.assertEqual(meta["phase"], "snapshot_metadata_matches_not_promoted")
        self.assertEqual(meta["verification"], "metadata_only")
        self.assertNotIn("downloads", meta["snapshot"])
        self.gh.downloads[TAG, ARCHIVE] = self.gh.archive[:-1] + b"b"
        out = self.read(True)
        self.assertEqual(out["snapshot"]["state"], "metadata_match")
        self.assertEqual(out["snapshot"]["downloads"][ARCHIVE], "mismatch")
        self.assertEqual(out["phase"], "staged_snapshot_not_public_or_incomplete")

    def test_no_promote_recommendation_for_stale_or_wrong_marker(self):
        self.gh.releases[TAG] = self.gh.assets(TARGET, TAG, True)
        self.gh.parents_of[TARGET] = [STALE]
        self.assertEqual(self.read()["phase"], "snapshot_not_current_release_or_direct_child")
        self.gh.files[TARGET][MARKER] = b"v41.999\n"
        self.assertEqual(self.read()["phase"], "invalid_snapshot_marker")

    def test_missing_metadata_digest_is_not_equivalent_to_verified(self):
        self.gh.releases[TAG] = self.gh.assets(TARGET, TAG, True)
        self.gh.releases[TAG]["assets"][-1]["digest"] = None
        self.assertEqual(self.read()["snapshot"]["assets"][ARCHIVE], "digest_unavailable")

    def test_download_catches_sidecar_drift_even_if_metadata_and_dat_match(self):
        self.gh.releases[TAG] = self.gh.assets(TARGET, TAG, True)
        self.gh.release_tip = TARGET
        self.gh.releases[ROLLING] = self.gh.assets(TARGET, ROLLING)
        self.gh.downloads[ROLLING, QUALITY] = b"quality bad\n"
        out = self.read(True)
        self.assertEqual(out["rolling"]["downloads"][DAT], "verified")
        self.assertEqual(out["rolling"]["downloads"][QUALITY], "mismatch")
        self.assertEqual(out["phase"], "promoted_rolling_incomplete_or_stale")

    def test_duplicate_or_starter_asset_is_not_eligible(self):
        self.gh.releases[TAG] = self.gh.assets(TARGET, TAG, True)
        archive = self.gh.releases[TAG]["assets"][-1]
        archive["state"] = "starter"
        self.assertEqual(self.read()["snapshot"]["assets"][ARCHIVE], "not_uploaded")
        self.gh.releases[TAG]["assets"].append(dict(archive))
        self.assertEqual(self.read()["snapshot"]["assets"][ARCHIVE], "ambiguous")

    def test_promoted_release_missing_its_archive_requires_investigation(self):
        self.gh.release_tip = TARGET
        self.gh.releases[TAG] = self.gh.assets(TARGET, TAG)
        self.assertEqual(self.read()["phase"], "promoted_snapshot_needs_investigation")

    def test_readback_detects_a_ref_race(self):
        calls = iter((TIP, STALE))
        self.gh.tip = lambda: next(calls)
        self.assertEqual(self.read()["phase"], "refs_changed_during_readback")


if __name__ == "__main__":
    unittest.main()
