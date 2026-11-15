import base64
import contextlib
import io
import hashlib
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch

import audit_v41_cdn_public as audit

REPO = "example/geoip"
SHA = "b" * 40


class PublicCdnAuditTests(unittest.TestCase):
    def setUp(self):
        self.blobs = {name: name.encode() + b"\0" for name in audit.FILES}
        self.calls = []
        self.rows = [
            {"name": name, "type": "file", "size": len(data),
             "hash": base64.b64encode(hashlib.sha256(data).digest()).decode()}
            for name, data in self.blobs.items()
        ]
        self.flat = [{**row, "name": "/" + row["name"]} for row in self.rows]
        self.stale = set()
        self.git_tree = {"truncated": False, "tree": [
            {"path": n, "size": len(d), "mode": "100644", "type": "blob"}
            for n, d in self.blobs.items()
        ]}

    def fetch(self, url, limit):
        self.calls.append(url)
        if url == f"https://api.github.com/repos/{REPO}/git/trees/{SHA}":
            return json.dumps(self.git_tree).encode()
        if url.startswith("https://data.jsdelivr.com/"):
            rows = self.flat if url.endswith("/flat") else self.rows
            return json.dumps({"files": rows}).encode()
        name = url.rsplit("/", 1)[1]
        if name.endswith(".sha256sum"):
            binary = name.removesuffix(".sha256sum")
            digest = hashlib.sha256(self.blobs[binary]).hexdigest()
            data = f"{digest}  {binary}\n".encode()
        else:
            data = self.blobs[name]
        return b"stale" if url in self.stale else data

    def check(self, **opts):
        return audit.audit(REPO, SHA, audit.EDGES, self.fetch, **opts)

    def test_inventory_checks_pinned_raw_and_all_requested_cdn_downloads(self):
        result = self.check()
        self.assertEqual(len(self.calls), 14)
        self.assertEqual(result["verified_hosts"], ["raw.githubusercontent.com", *audit.EDGES])
        self.assertEqual(set(result["files"]), set(audit.FILES))
        self.assertEqual(result["cdn_commit"], SHA)
        for name in audit.FILES:
            self.assertIn(f"https://raw.githubusercontent.com/{REPO}/{SHA}/{name}", self.calls)

    def test_extra_source_dat_is_rejected_even_with_right_extension(self):
        self.rows.append({**self.rows[0], "name": "hydra-geoip.dat"})
        with self.assertRaisesRegex(ValueError, "unexpected or duplicate"):
            self.check()
        self.assertEqual(len(self.calls), 1)

    def test_no_missing_duplicates_or_directory_entries(self):
        original = self.rows[:]
        for rows in (original[:-1], original + [original[0]],
                     [{**original[0], "type": "directory"}, *original[1:]]):
            with self.subTest(rows=rows):
                self.rows = rows
                with self.assertRaises(ValueError):
                    self.check()

    def test_metadata_disagreement_and_stale_edge_are_rejected(self):
        self.flat[0]["size"] += 1
        with self.assertRaisesRegex(ValueError, "inventories disagree"):
            self.check()
        self.flat[0]["size"] -= 1
        self.stale.add(f"https://gcore.jsdelivr.net/gh/{REPO}@cdn/geoip_RU.srs")
        with self.assertRaisesRegex(ValueError, "geoip_RU.srs at gcore.jsdelivr.net"):
            self.check()

    def test_same_metadata_does_not_hide_stale_pinned_origin(self):
        self.stale.add(f"https://raw.githubusercontent.com/{REPO}/{SHA}/geoip_RU.dat")
        with self.assertRaisesRegex(ValueError, "geoip_RU.dat at raw.githubusercontent.com"):
            self.check()

    def test_cutover_checks_release_raw_and_its_checksums(self):
        release = "c" * 40
        result = self.check(release_commit=release)
        self.assertEqual(result["release_commit"], release)
        self.assertEqual(len(self.calls), 26)
        for name in audit.FILES:
            base = f"https://raw.githubusercontent.com/{REPO}/{release}/{name}"
            self.assertIn(base, self.calls)
            self.assertIn(base + ".sha256sum", self.calls)
            rolling = f"https://github.com/{REPO}/releases/download/latest-geoip-client-v41/{name}"
            self.assertIn(rolling, self.calls)
            self.assertIn(rolling + ".sha256sum", self.calls)

    def test_consistently_stale_cdn_relative_to_release_is_rejected(self):
        release = "c" * 40
        self.stale.add(f"https://raw.githubusercontent.com/{REPO}/{release}/geoip_RU.srs")
        with self.assertRaisesRegex(ValueError, "promoted release"):
            self.check(release_commit=release)

    def test_bad_release_sidecar_is_rejected(self):
        release = "c" * 40
        self.stale.add(f"https://raw.githubusercontent.com/{REPO}/{release}/geoip_RU.dat.sha256sum")
        with self.assertRaisesRegex(ValueError, "promoted release checksum"):
            self.check(release_commit=release)

    def test_consistent_git_and_cdn_do_not_hide_stale_rolling_download(self):
        base = f"https://github.com/{REPO}/releases/download/latest-geoip-client-v41/"
        for name in ("geoip_RU.srs", "geoip_RU.srs.sha256sum"):
            with self.subTest(name=name):
                self.stale = {base + name}
                with self.assertRaisesRegex(ValueError, "rolling GitHub Release"):
                    self.check(release_commit="c" * 40)

    def test_main_rejects_a_ref_change_in_either_branch(self):
        release = "c" * 40
        for release_after, cdn_after in (("d" * 40, SHA), (release, "d" * 40)):
            with self.subTest(release=release_after, cdn=cdn_after):
                stdout, stderr = io.StringIO(), io.StringIO()
                cli = ["audit", "--repo", REPO, "--compare-release"]
                with patch.object(audit.sys, "argv", cli), \
                        patch.object(audit, "get_commit", side_effect=(SHA, release, release_after, cdn_after)), \
                        patch.object(audit, "audit", return_value={"files": {}}), \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(audit.main(), 1)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("branch moved during audit", stderr.getvalue())

    def test_expected_release_is_checked_even_when_cdn_sha_is_unchanged(self):
        expected_release, newer_release = "c" * 40, "d" * 40
        cli = ["audit", "--repo", REPO, "--cdn-sha", SHA, "--release-sha", expected_release]
        for actual_release, status in ((newer_release, 1), (expected_release, 0)):
            with self.subTest(actual_release=actual_release):
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(audit.sys, "argv", cli), \
                        patch.object(audit, "get_commit",
                                     side_effect=lambda _, branch: actual_release if branch == "release" else SHA), \
                        patch.object(audit, "audit", return_value={"files": {}}) as run, \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(audit.main(), status)
                if status:
                    run.assert_not_called()
                    self.assertIn("does not match expected release", stderr.getvalue())
                else:
                    run.assert_called_once_with(REPO, SHA, audit.CANONICAL,
                                               release_commit=expected_release)

    def test_snapshot_marker_is_pinned_to_the_promoted_commit(self):
        release, tag = "c" * 40, "geoip-v41-snapshot-42.1"
        raw = f"{tag}\n".encode()
        snapshots = {
            "valid": (raw, tag, release, None),
            "tag-mismatch": (raw, "v41.2", release, "does not match expected tag"),
            "moved-tag": (raw, tag, SHA, "does not point"),
            "rolling-alias": (b"latest-geoip-client-v41\n", None, release, "not the rolling alias"),
            "no-newline": (tag.encode(), tag, release, "noncanonical"),
            "too-many-lines": (raw + b"v41.2\n", None, release, "expected a versioned"),
        }
        for label, (marker, expected, tag_commit, err) in snapshots.items():
            with self.subTest(label=label), patch.object(audit, "get_tag_commit", return_value=tag_commit):
                def fetch(url, limit):
                    self.assertEqual(url, f"https://raw.githubusercontent.com/{REPO}/{release}/{audit.SNAPSHOT_MARKER}")
                    self.assertEqual(limit, 128)
                    return marker
                if err:
                    with self.assertRaisesRegex(ValueError, err):
                        audit.checked_snapshot_tag(REPO, release, expected, fetch)
                else:
                    self.assertEqual(audit.checked_snapshot_tag(REPO, release, expected, fetch), tag)

    def test_resolves_both_lightweight_and_annotated_tags(self):
        tag = "v41.2"
        ref = "refs/tags/" + tag
        for lines, expected in ((f"{SHA}\t{ref}\n", SHA),
                                (f"{SHA}\t{ref}\n{'c' * 40}\t{ref}^{{}}\n", "c" * 40)):
            with self.subTest(lines=lines), patch.object(
                audit.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=lines)
            ) as git:
                self.assertEqual(audit.get_tag_commit(REPO, tag), expected)
                self.assertEqual(git.call_args.args[0][-2:], [ref, ref + "^{}"])

    def test_fallback_checks_all_binaries_and_sidecars(self):
        release, tag = "c" * 40, "v41.2"
        base = f"https://github.com/{REPO}/releases/download/{tag}/"
        result = self.check(release_commit=release, versioned_tag=tag)
        self.assertEqual(len(self.calls), 32)
        self.assertEqual(result["versioned_snapshot_verified"], tag)
        for name in audit.FILES:
            self.assertIn(base + name, self.calls)
            self.assertIn(base + name + ".sha256sum", self.calls)
        for filename, kind in (("geoip_RU.srs", "bytes"), ("geoip_PRIVATE.srs.sha256sum", "checksum")):
            with self.subTest(filename=filename):
                self.stale = {base + filename}
                with self.assertRaisesRegex(ValueError, f"versioned GitHub snapshot {kind} differ"):
                    self.check(release_commit=release, versioned_tag=tag)

    def test_rejects_a_tag_changed_after_bytes_were_read(self):
        release, tag = "c" * 40, "v41.2"
        cli = ["audit", "--repo", REPO, "--cdn-sha", SHA, "--snapshot-tag", tag]
        with patch.object(audit.sys, "argv", cli), \
                patch.object(audit, "get_commit", side_effect=lambda _, branch: release if branch == "release" else SHA), \
                patch.object(audit, "checked_snapshot_tag", return_value=tag), \
                patch.object(audit, "get_tag_commit", return_value="d" * 40), \
                patch.object(audit, "audit", return_value={}), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(audit.main(), 1)
        self.assertIn("tag moved during audit", err.getvalue())

    def test_fallback_only_ignores_rolling_and_cdn(self):
        release, tag = "c" * 40, "v41.2"
        self.stale.add(f"https://github.com/{REPO}/releases/download/latest-geoip-client-v41/geoip_RU.dat")
        result = audit.audit_fallback(REPO, release, tag, self.fetch)
        self.assertEqual(result["scope"], "versioned GitHub fallback only")
        self.assertEqual(len(self.calls), 12)
        self.assertTrue(all(url.startswith((
            f"https://raw.githubusercontent.com/{REPO}/{release}/",
            f"https://github.com/{REPO}/releases/download/{tag}/",
        )) for url in self.calls))

    def test_fallback_only_cli_never_resolves_the_cdn_ref(self):
        release, tag = "c" * 40, "v41.2"
        cli = ["audit", "--repo", REPO, "--release-sha", release,
               "--snapshot-tag", tag, "--fallback-only"]
        result = {"scope": "versioned GitHub fallback only"}
        stdout = io.StringIO()
        with patch.object(audit.sys, "argv", cli), \
                patch.object(audit, "get_commit", return_value=release) as refs, \
                patch.object(audit, "checked_snapshot_tag", return_value=tag), \
                patch.object(audit, "get_tag_commit", return_value=release), \
                patch.object(audit, "audit", side_effect=AssertionError("unexpected CDN check")), \
                patch.object(audit, "audit_fallback", return_value=result) as fallback, \
                contextlib.redirect_stdout(stdout):
            self.assertEqual(audit.main(), 0)
        self.assertEqual(json.loads(stdout.getvalue()), result)
        self.assertEqual([item.args for item in refs.call_args_list], [(REPO, "release")] * 2)
        fallback.assert_called_once_with(REPO, release, tag)

    def test_historical_fallback_is_explicit_and_never_reads_mutable_refs(self):
        release, tag = "c" * 40, "v41.2"
        cli = ["audit", "--repo", REPO, "--historical-snapshot", "--fallback-only",
               "--release-sha", release, "--snapshot-tag", tag]
        stdout = io.StringIO()
        with patch.object(audit.sys, "argv", cli), \
                patch.object(audit, "get_commit",
                             side_effect=AssertionError("unexpected mutable ref read")), \
                patch.object(audit, "checked_snapshot_tag", return_value=tag) as marker, \
                patch.object(audit, "get_tag_commit", return_value=release), \
                patch.object(audit, "audit_fallback", return_value={"files": {}}), \
                contextlib.redirect_stdout(stdout):
            self.assertEqual(audit.main(), 0)
        marker.assert_called_once_with(REPO, release, tag)
        self.assertEqual(json.loads(stdout.getvalue())["scope"], "specified historical GitHub snapshot only")

    def test_historical_fallback_requires_both_explicit_pins_and_fallback_only(self):
        args = ["--historical-snapshot", "--fallback-only", "--release-sha", "c" * 40,
                "--snapshot-tag", "v41.2"]
        for omitted in ("--release-sha", "--snapshot-tag", "--fallback-only"):
            cli = args.copy()
            index = cli.index(omitted)
            del cli[index:index + (1 if omitted == "--fallback-only" else 2)]
            with self.subTest(omitted=omitted), patch.object(audit.sys, "argv", ["audit", *cli]), \
                    contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as stopped:
                audit.main()
            self.assertEqual(stopped.exception.code, 2)
            self.assertIn("--historical-snapshot requires", err.getvalue())

    def test_pinned_git_tree_agrees_with_both_public_inventories(self):
        result = self.check(verify_git_tree=True)
        self.assertTrue(result["pinned_git_tree_verified"])
        self.assertEqual(len(self.calls), 15)
        self.assertIn(f"https://api.github.com/repos/{REPO}/git/trees/{SHA}", self.calls)

    def test_cached_inventories_cannot_hide_an_extra_git_tree_entry(self):
        payloads = [
            {"path": "notes", "mode": "040000", "type": "tree"},
            {"path": "journal.md", "mode": "100644", "type": "blob", "size": 10},
        ]
        for extra in payloads:
            with self.subTest(extra=extra):
                self.git_tree["tree"].append(extra)
                with self.assertRaisesRegex(ValueError, "unexpected files or modes"):
                    self.check(verify_git_tree=True)
                self.git_tree["tree"].pop()

    def test_git_tree_requires_all_files_untruncated_and_at_exact_sizes(self):
        self.git_tree["truncated"] = True
        with self.assertRaisesRegex(ValueError, "is truncated"):
            self.check(verify_git_tree=True)
        self.git_tree["truncated"] = False
        self.git_tree["tree"][0]["size"] += 1
        with self.assertRaisesRegex(ValueError, "differs from public inventory"):
            self.check(verify_git_tree=True)
        self.git_tree["tree"].pop()
        with self.assertRaisesRegex(ValueError, "differs from public inventory"):
            self.check(verify_git_tree=True)

    def test_inventory_matches_the_shell_publisher(self):
        shell = Path(audit.__file__).with_name("v41_cdn_files.sh").read_text()
        line = next(line for line in shell.splitlines() if "V41_CDN_FILES=" in line)
        self.assertEqual(set(line.partition("(")[2].partition(")")[0].split()), set(audit.FILES))


if __name__ == "__main__":
    unittest.main()
