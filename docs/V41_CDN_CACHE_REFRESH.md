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

Only the production v41 job publishes the CDN branch, after publishing and
verifying the release. It derives a fresh tree from the three checked
GitHub blobs, never from an unrestricted copy of `release`. The branch
starts from a root commit and subsequent updates are fast-forward and
compare-and-swap protected. Unchanged bytes do not create another commit.
GitHub checksum sidecars are checked before the branch moves. They are not
part of the CDN payload.

The best-effort purge attempts all three rolling URLs and checks the exact
response path and reported provider confirmations. A separate bounded
public read-back compares what jsDelivr serves against the new bytes.
If it reports a failure, use the run-specific GitHub Release and its
checksums. A GitHub release may still be edited unless the repository
enforces immutable releases.

For a manual retry of the cache refresh only, first confirm the intended
`cdn` commit, then run the script from the source checkout.

```sh
GITHUB_REPOSITORY=SpeedeMiner/Geoip-ru-server bash .github/scripts/purge_v41_jsdelivr.sh
```

[Publication journal](V41_CDN_PUBLICATION_JOURNAL_20261115.md).
