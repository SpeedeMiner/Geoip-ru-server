# v41 release recovery and read-only checks

This procedure is for the workflow proposed in Draft PR #32, commit
`9d063520`. It is not an instruction to release that PR. No operational write
was tested against GitHub in this pass. The older production workflow has no
retained archive marker and must be interpreted separately.

## Establish the state before retrying

Read the exact versioned tag shown by the failed job. Do not use a rolling tag
or an assumed version. Run from the audit branch:

```sh
python3 docs/tools/read_v41_release_state.py geoip-v41-snapshot-43587602958.1
python3 docs/tools/read_v41_release_state.py geoip-v41-snapshot-43587602958.1 --verify-downloads
python3 -m unittest discover -s docs/tools -p 'test_read_v41_release_state.py' -v
```

Replace the example tag with the run's actual tag. The example is a **legacy**
snapshot and is intentionally expected to lack a retained ipverse archive.
The first command uses the GitHub API's asset size and SHA-256 metadata, pinned
Git files, and the committed DAT checksum/manifest. The second additionally
downloads and hashes all tracked public assets. The rolling check covers
the DAT, DAT checksum, manifest, quality report, input provenance and effective
block-mask checksum. It is a diagnostic subset of the rolling asset list, not
a certification of all assets. The versioned check covers all four legacy
snapshot assets plus the retained archive when the marker exists.

A missing public Release entry cannot distinguish a Git tag with no Release
from a tag with an unpublished draft. GitHub documents the
[by-tag endpoint as published-release only](https://docs.github.com/en/rest/releases/releases#get-a-release-by-tag-name).
An operator with push access can inspect drafts separately using the Releases
page or the authenticated [list endpoint](https://docs.github.com/en/rest/releases/releases#list-releases).
No draft creation, editing, deletion or asset upload is done by the inspector.

## Interpret the result

| Inspector phase | What to do |
| --- | --- |
| `no_snapshot_tag` | The proposed snapshot tag did not reach GitHub. Diagnose the failing stage before a new run. |
| `legacy_snapshot` | The tag predates archive retention. Lack of the archive is expected. Any legacy audit still requires the exact compressed bytes in this commit's provenance. |
| `staged_snapshot_not_public_or_incomplete` | The new tag is on a direct child of `release`, but publication or readback is incomplete. Leave `release` alone. Preserve the original candidate artifact and job logs. |
| `snapshot_metadata_matches_not_promoted` | Asset metadata matches and the tag is a direct child, but actual downloads were not checked. Run with `--verify-downloads`. |
| `snapshot_verified_not_promoted` | All tracked snapshot downloads matched their exact checksums. Check whether the run stopped or the expected parent changed. Do not push a stale candidate by hand. |
| `snapshot_not_current_release_or_direct_child` | This may be an old successful tag or a competing/stale candidate. It is not eligible for the workflow's direct-child promotion. |
| `promoted_rolling_matches` | The tag equals the release branch tip and all tracked rolling assets match at the selected verification level. |
| `promoted_rolling_incomplete_or_stale` | The versioned snapshot is valid, but one or more rolling assets are missing, stale or unavailable. The Git snapshot and rolling GitHub Release are separate publication surfaces. |
| `promoted_snapshot_needs_investigation` | The branch already points to a snapshot with missing or invalid evidence. Preserve the tag and compare the pinned provenance and original artifact. Do not fall back to newer upstream data. |
| `refs_changed_during_readback` / `invalid_snapshot_marker` | Retry read-only verification once refs stabilize, or investigate the marker in the pinned commit. Do not act on this result. |

The default supported retry after a failed snapshot upload is a new validated
run using a new automatic tag or another unused explicit version. Do not move
the existing tag or replace an already published snapshot asset. A rerun with
the same explicit version will encounter the existing tag and intentionally
stop. The GitHub CLI uploads assets using separate API requests and may leave
a draft if interrupted, as documented under
[gh release create](https://cli.github.com/manual/gh_release_create). If an
operator needs to preserve an already exposed version, first inspect the draft
and recover the exact original Actions candidate while it still exists. Check
both the recorded archive size and SHA-256, plus the tag's commit identity.
A same-member archive recreated from a commit URL is not the original bytes.

If promotion succeeded and rolling upload failed, prefer the versioned
snapshot for verification while investigating the failed rolling job. Never
infer success from the DAT hash alone. The v41 manifest and quality report
contain build-specific information and can remain stale even when the DAT is
identical. Avoid bulk asset replacement based only on metadata or a guessed
run artifact. Any deliberate rolling repair needs the exact matching validated
artifact and another complete readback.

## Rehearsal evidence

On 2026-11-14 the actual `release` commit `de20de62` and its versioned tag
`geoip-v41-snapshot-43587602958.1` agreed. The Git tree and public asset metadata
matched for all tracked legacy snapshot and rolling files. The production
archive provenance was independently rechecked against the original public
upstream URL. No production tags, branches or releases were modified.
