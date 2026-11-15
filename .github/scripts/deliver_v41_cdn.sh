#!/usr/bin/env bash
set -euo pipefail

scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir "$tmp/binaries"
bash "$scripts/verify_v41_cdn_github_release.sh" "$SNAPSHOT_SHA" "$tmp/binaries"
output="$tmp/output"
# Publishing the branch is a required Git update.
GITHUB_OUTPUT="$output" bash "$scripts/publish_v41_cdn_branch.sh"
IFS= read -r result < "$output"
[[ "$result" =~ ^cdn_sha=([0-9a-f]{40})$ ]]
export CDN_SHA="${BASH_REMATCH[1]}"
# Confirm the pushed commit reached GitHub's download edge before asking the
# cache to repopulate. The public read-back still checks the branch alias.
readback() {
  (cd "$tmp/binaries" && bash "$scripts/verify_v41_cdn_readback.sh" "$1")
}
if ! readback pinned; then
  if [[ "${V41_REQUIRE_CDN_READBACK:-0}" == 1 ]]; then
    echo "::error::CDN ref $CDN_SHA is set, but GitHub Raw did not confirm it. Use GitHub Release, skipping jsDelivr purge. Retry repair."
    exit 1
  fi
  echo "::warning::CDN ref $CDN_SHA is set, but GitHub Raw did not confirm it. Use GitHub Release, skipping jsDelivr purge."
  printf 'cdn_sha=%s\n' "$CDN_SHA" >> "$GITHUB_OUTPUT"
  exit 0
fi
if ! bash "$scripts/purge_v41_jsdelivr.sh"; then
  echo "::warning::jsDelivr purge was not confirmed for all client files"
fi
if ! readback public; then
  if [[ "${V41_REQUIRE_CDN_READBACK:-0}" == 1 ]]; then
    echo "::error::CDN ref $CDN_SHA is set, but public CDN bytes were not confirmed. Use GitHub Release and retry repair."
    exit 1
  fi
  echo "::warning::jsDelivr public bytes were not confirmed. Use GitHub Release."
fi
printf 'cdn_sha=%s\n' "$CDN_SHA" >> "$GITHUB_OUTPUT"
