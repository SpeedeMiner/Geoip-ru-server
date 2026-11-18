# v41 client-only jsDelivr delivery

The supported CDN alias is the `cdn` branch. It contains four client binaries and the RU MRS sidecar.

| Client | Rolling URL |
| --- | --- |
| Xray | [geoip_RU.dat](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.dat) |
| sing-box RU | [geoip_RU.srs](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.srs) |
| sing-box PRIVATE | [geoip_PRIVATE.srs](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_PRIVATE.srs) |
| mihomo RU | [geoip_RU.mrs](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.mrs) |
| mihomo RU checksum | [geoip_RU.mrs.sha256sum](https://cdn.jsdelivr.net/gh/SpeedeMiner/Geoip-ru-server@cdn/geoip_RU.mrs.sha256sum) |

Only the RU MRS sidecar is mirrored. Other checksums, source DATs, manifests,
archives and audit reports stay on GitHub. PRIVATE MRS is not part of any release.
Old `@release` CDN links are not refreshed or supported. This design
does not revoke previously cached URLs or stop someone from requesting a
different public GitHub ref through a third-party cache.

The production v41 job publishes the CDN branch after publishing and
verifying the release. The manual repair path reuses an existing release.
Both compare the public rolling GitHub assets with the promoted release
commit before writing to CDN. A production run also checks the fallback tag,
the snapshot marker and the versioned downloads before updating `cdn`.
The separate repair workflow reuses the verified rolling release. Both
derive a fresh tree from the allowlisted, checked
GitHub blobs, never from an unrestricted copy of `release`. The branch
starts from a root commit and subsequent updates are fast-forward and
compare-and-swap protected. Unchanged bytes do not create another commit.
GitHub checksum sidecars are checked before the branch moves. The first
RU MRS publication can upgrade the exact legacy three-file CDN tree in place.

After the Git update, both paths wait for GitHub Raw to serve all five files
from the exact CDN commit. If that check fails, they skip the cache purge.
The best-effort purge then attempts the five rolling URLs and checks the
response paths and provider confirmations. Even if purge fails, a bounded
public read-back independently compares what jsDelivr serves with the new bytes.
The Actions summary reports whether the origin or public CDN was unconfirmed
and points to the GitHub Release fallback. Production links to the exact
versioned snapshot published by that run. The standalone repair links to
the current rolling GitHub Release it just verified. The production job only prints
jsDelivr download URLs as verified when all five public downloads match.
A GitHub release may still be edited unless the repository enforces immutable
releases.

## Move clients from `@release` to `@cdn`

- For this repository's Xray DAT or sing-box rule-set URL, replace only
  `@release` with `@cdn`. Keep the filename and client rule configuration.
- Only the RU MRS checksum uses a jsDelivr URL. Leave other checksum and
  audit URLs on GitHub Release or GitHub Raw.
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

Before touching `cdn`, repair checks the four client binaries and
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
python3 .github/scripts/audit_v41_cdn_public.py --edges --verify-git-tree --verify-snapshot
```

This read-only command uses git to resolve the current `cdn` commit and
requires the jsDelivr tree and flat inventories to contain exactly the
five CDN files. It compares their hashes and sizes with pinned GitHub
Raw and the actual CDN downloads. With `--edges` it also checks Fastly and
Gcore. With `--compare-release` it also reads all four binaries and sidecars
from both the current pinned release commit and the rolling GitHub Release
asset URLs. It fails if either branch moves during the check. Without this flag it checks internal CDN consistency only.
When verifying a specific publication, pass both `--cdn-sha` and
`--release-sha` from its publish log. The latter also enables release
comparison without requiring `--compare-release`. The `--verify-snapshot`
flag also verifies the exact versioned fallback and its checksums using the
tag recorded in the promoted release. To check a specific run, pass its
`--snapshot-tag` explicitly. Use `--fallback-only` to check the versioned
GitHub assets and promoted Git commit while skipping the CDN and rolling
GitHub downloads, for example during a CDN outage. The optional
`--verify-git-tree` also reads the GitHub root tree for the pinned CDN commit
so an old jsDelivr index cannot hide an extra entry in a new commit. This flag
uses the public, unauthenticated GitHub API and does not require a token.
A mismatch exits nonzero. During normal cache propagation, retry or use
GitHub Release directly. This command neither purges nor changes a ref.

When the CDN index and actual downloads disagree, run the optional
plane-by-plane diagnostic:

```sh
python3 .github/scripts/audit_v41_cdn_public.py --diagnose-planes --edges --verify-snapshot
```

The reference is the exact five-file Git tree and its pinned Raw blobs,
verified against their Git object IDs and then hashed with SHA-256. The
report compares rolling and SHA-pinned tree/flat catalogs, checks every
expected download from the selected endpoints, and verifies the promoted
and rolling GitHub Release. Here `--verify-snapshot` adds the versioned
fallback. An outdated catalog is reported separately from outdated
download bytes. Either still fails the command. This flag only adds
read-only diagnostics and is not used by the publishing workflows.

[Cutover runbook](V41_CDN_CUTOVER_RUNBOOK.md) · [Publication journal](V41_CDN_PUBLICATION_JOURNAL_20261115.md).
