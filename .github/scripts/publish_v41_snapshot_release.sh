#!/usr/bin/env bash
set -euo pipefail

# Create-only. Do not fall back to a command that edits an existing release
# or replaces its assets. The Git tag exists, but release has not advanced.
[[ "$SNAPSHOT_TAG" =~ ^(v41\.(0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]+\.[0-9]+)$ ]]
srs_assets=(geoip_RU.srs geoip_RU.srs.sha256sum geoip_PRIVATE.srs geoip_PRIVATE.srs.sha256sum)
for asset in "$V41_OUTPUT_FILE" "$OUTPUT_SHA_FILE" "$V41_MANIFEST" "$V41_QUALITY_REPORT" "$IPVERSE_BGP_ARCHIVE" "$REGISTRY_INPUTS_ARCHIVE" "$UPSTREAM_INPUTS_ARCHIVE" "$BLOCK_INPUTS_ARCHIVE" "$RELEASE_MANIFEST" "$INPUT_PROVENANCE" "${srs_assets[@]}"; do
  if [[ ! -f "$asset" || ! -r "$asset" || ! -s "$asset" ]]; then
    printf 'Missing, unreadable or empty snapshot asset: %s\n' "$asset" >&2
    exit 1
  fi
done
# Recheck the extra input again at the API boundary. The provenance sidecar
# belongs to the exact release tree and was already verified at preflight.
python3 "$(dirname "${BASH_SOURCE[0]}")/verify_v41_ipverse_archive.py" \
  --provenance "$INPUT_PROVENANCE" --archive "$IPVERSE_BGP_ARCHIVE"
sha256sum -c "$REGISTRY_INPUTS_SHA"
python3 "$(dirname "${BASH_SOURCE[0]}")/bundle_v41_registry_inputs.py" verify \
  "$INPUT_PROVENANCE" "$REGISTRY_INPUTS_ARCHIVE"
sha256sum -c "$UPSTREAM_INPUTS_SHA"
python3 "$(dirname "${BASH_SOURCE[0]}")/bundle_v41_registry_inputs.py" \
  --upstream-catalog "$(dirname "${BASH_SOURCE[0]}")/../data/v41-upstream-sources.json" verify \
  "$INPUT_PROVENANCE" "$UPSTREAM_INPUTS_ARCHIVE"
sha256sum -c "$BLOCK_INPUTS_SHA"
python3 "$(dirname "${BASH_SOURCE[0]}")/bundle_v41_registry_inputs.py" --block-inputs verify \
  "$INPUT_PROVENANCE" "$BLOCK_INPUTS_ARCHIVE"
python3 "$(dirname "${BASH_SOURCE[0]}")/v41_release_manifest.py" verify . --manifest "$RELEASE_MANIFEST"
gh release create "$SNAPSHOT_TAG" \
  "$V41_OUTPUT_FILE" "$OUTPUT_SHA_FILE" "$V41_MANIFEST" "$V41_QUALITY_REPORT" "$IPVERSE_BGP_ARCHIVE" "$REGISTRY_INPUTS_ARCHIVE" "$UPSTREAM_INPUTS_ARCHIVE" "$BLOCK_INPUTS_ARCHIVE" "$RELEASE_MANIFEST" "$INPUT_PROVENANCE" "${srs_assets[@]}" \
  --repo "$GITHUB_REPOSITORY" --verify-tag --latest=false \
  --title "GeoIP v41 snapshot $SNAPSHOT_TAG" \
  --notes "Validated snapshot of the release branch. This workflow does not update existing snapshots."
