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
If it reports a failure, use the run-specific GitHub Release and its
checksums. A GitHub release may still be edited unless the repository
enforces immutable releases.

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

[Publication journal](V41_CDN_PUBLICATION_JOURNAL_20261115.md).
