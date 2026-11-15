#!/usr/bin/env bash
set -euo pipefail

fallback_tag="${V41_CDN_FALLBACK_TAG:-latest-geoip-client-v41}"
if [[ ! "$fallback_tag" =~ ^(latest-geoip-client-v41|v41\.(0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]{1,20}\.[0-9]{1,10})$ ]]; then
  echo "::error::Unexpected GitHub Release fallback tag"
  exit 1
fi
scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir "$tmp/binaries"
bash "$scripts/verify_v41_cdn_github_release.sh" "$SNAPSHOT_SHA" "$tmp/binaries" "$fallback_tag"
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
strict="${V41_REQUIRE_CDN_READBACK:-0}"
purge="skipped"
status="origin_unconfirmed"
if readback pinned; then
  if bash "$scripts/purge_v41_jsdelivr.sh"; then
    purge="confirmed"
  else
    purge="not confirmed"
    echo "::warning::jsDelivr purge was not confirmed for all client files"
  fi
  if readback public; then
    status="verified"
  else
    status="public_unconfirmed"
  fi
fi

case "$status" in
  verified) description="all three client files verified on jsDelivr" ;;
  origin_unconfirmed) description="GitHub Raw not confirmed" ;;
  public_unconfirmed) description="public bytes not confirmed" ;;
esac
fallback="https://github.com/$GITHUB_REPOSITORY/releases/tag/$fallback_tag"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    printf '\n### jsDelivr delivery\n\n'
    printf '%s — %s, cache purge %s.\n\n' "\`$CDN_SHA\`" "$description" "$purge"
    printf '[GitHub Release fallback](%s)\n' "$fallback"
  } >> "$GITHUB_STEP_SUMMARY"
fi
if [[ "$status" != verified ]]; then
  severity=warning
  [[ "$strict" != 1 ]] || severity=error
  if [[ "$status" == origin_unconfirmed ]]; then
    echo "::$severity::CDN ref $CDN_SHA is set, but GitHub Raw did not confirm it. Use GitHub Release, skipping jsDelivr purge."
  else
    echo "::$severity::CDN ref $CDN_SHA is set, but public CDN bytes were not confirmed. Use GitHub Release."
  fi
  [[ "$strict" != 1 ]] || exit 1
fi
printf 'cdn_sha=%s\ncdn_status=%s\n' "$CDN_SHA" "$status" >> "$GITHUB_OUTPUT"
