#!/usr/bin/env bash
set -euo pipefail
sha256sum -c "$OUTPUT_SHA_FILE"
sha256sum -c geoip_RU.srs.sha256sum geoip_PRIVATE.srs.sha256sum
python3 ../.github/scripts/build_v41_srs.py
sha256sum -c "$V41_BLOCKED_SHA"
sha256sum -c "$BLOCK_INPUTS_SHA"
python3 ../.github/scripts/bundle_v41_registry_inputs.py --block-inputs verify \
  "$INPUT_PROVENANCE" "$BLOCK_INPUTS_ARCHIVE"
python3 ../.github/scripts/v41_release_manifest.py verify . --manifest "$RELEASE_MANIFEST"
sha256sum -c "$REGISTRY_INPUTS_SHA"
python3 ../.github/scripts/bundle_v41_registry_inputs.py verify \
  "$INPUT_PROVENANCE" "$REGISTRY_INPUTS_ARCHIVE"
python3 ../.github/scripts/verify_v41_ipverse_archive.py \
  --provenance "$INPUT_PROVENANCE" --archive "$IPVERSE_BGP_ARCHIVE"
sha256sum -c "$UPSTREAM_INPUTS_SHA"
python3 ../.github/scripts/bundle_v41_registry_inputs.py \
  --upstream-catalog ../.github/data/v41-upstream-sources.json verify \
  "$INPUT_PROVENANCE" "$UPSTREAM_INPUTS_ARCHIVE"
python3 ../.github/scripts/validate_v41_telegram.py --geoip "$V41_OUTPUT_FILE" --official-feed "$TELEGRAM_OFFICIAL_INPUT"
grep -q '^PRE_PUBLICATION_V41_HARD_POLICY_GATE$' "$V41_QUALITY_REPORT"
ref="$(git ls-remote --exit-code origin refs/heads/release | cut -f1)"
[[ "$ref" =~ ^[0-9a-f]{40}$ ]]
curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
  --connect-timeout 15 --max-time 90 --max-filesize 8388608 \
  "https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/${ref}/geoip_RU.dat" -o "$RUNNER_TEMP/previous-geoip.dat"
curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
  --connect-timeout 15 --max-time 90 --max-filesize 256 \
  "https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/${ref}/geoip_RU.dat.sha256sum" -o "$RUNNER_TEMP/previous-geoip.sha"
expected="$(awk 'NR==1 {print $1}' "$RUNNER_TEMP/previous-geoip.sha")"
[[ "$expected" =~ ^[0-9a-f]{64}$ ]]
printf '%s  %s\n' "$expected" "$RUNNER_TEMP/previous-geoip.dat" | sha256sum -c -
python3 ../.github/scripts/validate_v41_publication_bounds.py \
  --candidate "$V41_OUTPUT_FILE" --reference "$RUNNER_TEMP/previous-geoip.dat" \
  --reviewed-sha256 "$REVIEWED_SHA" | tee -a "$GITHUB_STEP_SUMMARY"
printf 'PREVIOUS_RELEASE_SHA=%s\n' "$ref" >> "$GITHUB_ENV"
