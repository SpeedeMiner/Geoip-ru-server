# GeoIP v41 CDN cutover runbook

The supported client channel is `SpeedeMiner/Geoip-ru-server@cdn`.
It distributes only `geoip_RU.dat`, `geoip_RU.srs` and
`geoip_PRIVATE.srs`. Keep audit data, checksums and source downloads on GitHub.
This runbook does not instruct operators to invalidate or delete legacy caches.

## Before landing the change

1. Check that v41 CI and CDN lint passed for the reviewed code commit.
   The PR build job must not execute the production publish job.
2. Record the current remote `main`, `release` and `cdn` refs.
3. Run the read-only public audit from the reviewed checkout.

```sh
git ls-remote origin refs/heads/main refs/heads/release refs/heads/cdn
python3 .github/scripts/audit_v41_cdn_public.py --edges --verify-snapshot
```

A successful audit confirms that the current rolling GitHub assets, promoted
Git tree, versioned fallback and public CDN agree. It does not predict future
cache propagation.
As part of a post-run check, compare the `release_commit` printed by the
audit to `snapshot_sha` in that run. On an unchanged CDN payload, the CDN
SHA can legitimately stay the same even when the release SHA advances.

## After landing the change

1. Follow the existing v41 run triggered by the update to `main`. Do not
   start a duplicate production run just to refresh caches.
2. Find the versioned GitHub snapshot and CDN status in the job log or
   Actions summary. Treat the GitHub snapshot as the fallback for this update.
3. Set `CDN_SHA`, `RELEASE_SHA` and `SNAPSHOT_TAG` to the commits and
   exact GitHub snapshot tag shown by this run. Then re-run the audit.

```sh
python3 .github/scripts/audit_v41_cdn_public.py --edges --cdn-sha "$CDN_SHA" --release-sha "$RELEASE_SHA" --snapshot-tag "$SNAPSHOT_TAG"
```

| What the workflow reports | What to do |
| --- | --- |
| `verified` | The rolling downloads matched the expected client files. If the optional multi-edge audit still fails for an endpoint, use the versioned GitHub snapshot until that endpoint catches up. |
| `origin_unconfirmed` | The CDN Git ref was set, but pinned GitHub Raw was not confirmed. Purge was skipped. Check the GitHub release, then use the separate repair workflow if needed. |
| `public_unconfirmed` | The CDN Git ref was set, but jsDelivr did not confirm all bytes. Keep the versioned GitHub fallback and rerun the read-only audit before repairing. |
| Versioned fallback audit failed | Check the pinned marker, Git tag and versioned assets. Use a GitHub download only after its bytes and checksum have been verified. Do not repair CDN to fix a missing snapshot asset. |
| GitHub asset preflight failed | The CDN step must leave `cdn` unchanged. Inspect rolling GitHub assets and their checksums before attempting to repair the CDN. |

If jsDelivr or the mutable rolling GitHub download is unavailable, validate
only the fallback for the expected release. This command does not query the
CDN, the CDN branch or the rolling GitHub assets.

```sh
python3 .github/scripts/audit_v41_cdn_public.py --fallback-only --release-sha "$RELEASE_SHA" --snapshot-tag "$SNAPSHOT_TAG"
```

Passing this check verifies the versioned GitHub snapshot, not recovery of
the public CDN. The expected release must still be the promoted release unless
you explicitly verify a historical snapshot.

To inspect a previously deployed snapshot after a newer release, pass the
known historical release SHA and its exact tag. This verifies only that
snapshot, without reading any mutable release, rolling or CDN reference.

```sh
python3 .github/scripts/audit_v41_cdn_public.py --fallback-only --historical-snapshot --release-sha "$RELEASE_SHA" --snapshot-tag "$SNAPSHOT_TAG"
```

A historical DAT-only snapshot does not pass this three-file check. This
read-only mode neither changes the published version nor rolls back CDN.

When release bytes and checksums are correct, **Repair GeoIP v41 client CDN**
can repair the channel from an existing release. If the binary tree already matches,
it does not create a new CDN commit. Do not reset Git refs or edit published
checksum files to turn a failed read-back into success.

## Client configuration

Replace `@release` with `@cdn` only for the three supported filenames in
existing client configs for this repository. See the
[client URLs and verification notes](V41_CDN_CACHE_REFRESH.md).
Older URLs may still be retrievable. The new publishing workflow does not
advertise or refresh them. It does not revoke third-party caches.
