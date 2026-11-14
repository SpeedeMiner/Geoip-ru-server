# v41 rolling CDN cache refresh

The GitHub release and the rolling jsDelivr alias are separate delivery
paths. Cache refresh does not publish, roll back, or verify release bytes.
The v41 publisher runs it as a non-fatal step after release publication.

The script attempts all 22 compatibility URLs, even when an individual
request times out or the API does not confirm the purge. It verifies the
exact response path, completed status, the throttle flag and every reported
provider. GitHub Actions shows the confirmation count and failed filenames
in its job summary. A successful purge response is not a guarantee that
every observer sees the same bytes immediately.

If a refresh failed after GitHub publication, retry the cache step by
itself when the CDN recovers. No new build, release or tag is needed.
From the source checkout, after verifying the intended rolling branch:

```sh
GITHUB_REPOSITORY=SpeedeMiner/Geoip-ru-server bash .github/scripts/purge_v41_jsdelivr.sh
```

For consistent downloads, use the run-specific GitHub Release and verify
its SHA-256 sidecars. Do not mix files from the versioned Release with
hashes from a rolling CDN URL. The versioned link is preferable to a
rolling alias, but GitHub can still permit editing release assets unless
immutability is enforced by repository settings.
