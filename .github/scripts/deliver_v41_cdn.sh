#!/usr/bin/env bash
set -euo pipefail

scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir "$tmp/binaries"
bash "$scripts/verify_v41_cdn_github_release.sh" "$SNAPSHOT_SHA" "$tmp/binaries"
output="$tmp/output"
# Publishing the branch is a required Git update. A cache outage after the
# branch moves is advisory and must not turn a verified GitHub release into
# a failure. The two cache checks are independent, so both always run.
GITHUB_OUTPUT="$output" bash "$scripts/publish_v41_cdn_branch.sh"
IFS= read -r result < "$output"
[[ "$result" =~ ^cdn_sha=([0-9a-f]{40})$ ]]
export CDN_SHA="${BASH_REMATCH[1]}"
if ! bash "$scripts/purge_v41_jsdelivr.sh"; then
  echo "::warning::jsDelivr purge was not confirmed for all client files"
fi
if ! (cd "$tmp/binaries" && bash "$scripts/verify_v41_cdn_readback.sh"); then
  if [[ "${V41_REQUIRE_CDN_READBACK:-0}" == 1 ]]; then
    echo "::error::CDN ref $CDN_SHA is set, but public CDN bytes were not confirmed. Use GitHub Release and retry repair."
    exit 1
  fi
  echo "::warning::jsDelivr public bytes were not confirmed. Use GitHub Release."
fi
printf 'cdn_sha=%s\n' "$CDN_SHA" >> "$GITHUB_OUTPUT"
