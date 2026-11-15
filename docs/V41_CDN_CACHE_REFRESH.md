# v41 client-only jsDelivr delivery

The supported CDN alias is the `cdn` branch. It contains exactly three files.

| Client | Rolling URL |
| --- | --- |
| Xray | [geoip_RU.dat](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.dat) |
| sing-box RU | [geoip_RU.srs](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.srs) |
| sing-box PRIVATE | [geoip_PRIVATE.srs](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_PRIVATE.srs) |

Checksums, source DATs, manifests, archives and audit reports stay on GitHub.
The workflow never adds them to `cdn` or asks jsDelivr to refresh them.
Old `@release` CDN links are not refreshed or supported. This design
does not revoke previously cached URLs or stop someone from requesting a
different public GitHub ref through a third-party cache.

The production v41 job publishes the CDN branch after publishing and
verifying the release. The manual repair path reuses an existing release.
Both compare the public rolling GitHub assets with the promoted release
commit before writing to CDN. They derive a fresh tree from the three checked
GitHub blobs, never from an unrestricted copy of `release`. The branch
starts from a root commit and subsequent updates are fast-forward and
compare-and-swap protected. Unchanged bytes do not create another commit.
GitHub checksum sidecars are checked before the branch moves. They are not
part of the CDN payload.

After the Git update, both paths wait for GitHub Raw to serve all three files
from the exact CDN commit. If that check fails, they skip the cache purge.
The best-effort purge then attempts the three rolling URLs and checks the
response paths and provider confirmations. Even if purge fails, a bounded
public read-back independently compares what jsDelivr serves with the new bytes.
The Actions summary reports whether the origin or public CDN was unconfirmed
and points to the GitHub Release fallback. Production links to the exact
versioned snapshot published by that run. The standalone repair links to
the current rolling GitHub Release it just verified. The production job only prints
jsDelivr download URLs as verified when all three public downloads match.
A GitHub release may still be edited unless the repository enforces immutable
releases.

## Move clients from `@release` to `@cdn`

- For this repository's Xray DAT or sing-box rule-set URL, replace only
  `@release` with `@cdn`. Keep the filename and client rule configuration.
- Leave checksum and audit URLs on GitHub Release or GitHub Raw. Do not
  append a checksum suffix to a jsDelivr client URL.
- For a reproducible deployment, choose a versioned GitHub snapshot and
  verify the downloaded file using the checksum from that same snapshot.
  Do not mix a rolling binary with a checksum from another release.
- Removing the published legacy links and purge calls does not remove
  previously cached URLs. Other public GitHub refs are outside the
  scope of the client-only `@cdn` branch.

## Repair CDN from the current GitHub release

In GitHub Actions, run **Repair GeoIP v41 client CDN** on `main`. GitHub
offers this action once the workflow is present on the default branch.
It does not build GeoIP, retag anything, update `release`, or upload
GitHub assets. It waits in the same bounded queue as production v41,
so neither workflow replaces another queued production run.

Before touching `cdn`, repair checks the exact three client files and
their GitHub checksum sidecars against the promoted `release` commit.
If the GitHub rolling release is missing or out of sync, repair stops
without moving `cdn`. If the public CDN fails read-back after the branch
is updated, repair reports failure. Once GitHub is correct, running
repair again is safe and does not create an extra commit for the same bytes.

For a manual retry of the cache refresh only, first confirm the intended
`cdn` commit, then run the script from the source checkout.

```sh
GITHUB_REPOSITORY=SpeedeMiner/Geoip-ru-server bash .github/scripts/purge_v41_jsdelivr.sh
```

## Audit the public channel without publishing

```sh
python3 .github/scripts/audit_v41_cdn_public.py --edges --compare-release
```

This read-only command uses git to resolve the current `cdn` commit and
requires the jsDelivr tree and flat inventories to contain exactly the
three client files. It compares their hashes and sizes with pinned GitHub
Raw and the actual CDN downloads. With `--edges` it also checks Fastly and
Gcore. With `--compare-release` it also reads all three files and sidecars
from the current pinned release commit, and fails if either branch moves
during the check. Without this flag it checks internal CDN consistency only.
Use `--cdn-sha` when verifying a specific expected publication.
A mismatch exits nonzero. During normal cache propagation, retry or use
GitHub Release directly. This command neither purges nor changes a ref.

[Publication journal](V41_CDN_PUBLICATION_JOURNAL_20261115.md).
