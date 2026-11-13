#!/usr/bin/env bash
set -euo pipefail

# Create-only. Do not fall back to a command that edits an existing release
# or replaces its assets. The Git tag has already been pushed atomically.
[[ "$SNAPSHOT_TAG" =~ ^(v41\.(0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]+\.[0-9]+)$ ]]
gh release create "$SNAPSHOT_TAG" \
  "$V41_OUTPUT_FILE" "$OUTPUT_SHA_FILE" "$V41_MANIFEST" "$V41_QUALITY_REPORT" \
  --repo "$GITHUB_REPOSITORY" --verify-tag --latest=false \
  --title "GeoIP v41 snapshot $SNAPSHOT_TAG" \
  --notes "Validated snapshot of the release branch. This workflow does not update existing snapshots."
