#!/usr/bin/env bash
set -euo pipefail

# Create-only. Do not fall back to a command that edits an existing release
# or replaces its assets. The Git tag exists, but release has not advanced.
[[ "$SNAPSHOT_TAG" =~ ^(v41\.(0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]+\.[0-9]+)$ ]]
for asset in "$V41_OUTPUT_FILE" "$OUTPUT_SHA_FILE" "$V41_MANIFEST" "$V41_QUALITY_REPORT" "$IPVERSE_BGP_ARCHIVE"; do
  if [[ ! -f "$asset" || ! -r "$asset" || ! -s "$asset" ]]; then
    printf 'Missing, unreadable or empty snapshot asset: %s\n' "$asset" >&2
    exit 1
  fi
done
# Recheck the extra input again at the API boundary. The provenance sidecar
# belongs to the exact release tree and was already verified at preflight.
python3 "$(dirname "${BASH_SOURCE[0]}")/verify_v41_ipverse_archive.py" \
  --provenance "$INPUT_PROVENANCE" --archive "$IPVERSE_BGP_ARCHIVE"
gh release create "$SNAPSHOT_TAG" \
  "$V41_OUTPUT_FILE" "$OUTPUT_SHA_FILE" "$V41_MANIFEST" "$V41_QUALITY_REPORT" "$IPVERSE_BGP_ARCHIVE" \
  --repo "$GITHUB_REPOSITORY" --verify-tag --latest=false \
  --title "GeoIP v41 snapshot $SNAPSHOT_TAG" \
  --notes "Validated snapshot of the release branch. This workflow does not update existing snapshots."
