#!/usr/bin/env bash
set -euo pipefail

[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
[[ "$CDN_SHA" =~ ^[0-9a-f]{40}$ ]]
source "$(dirname "${BASH_SOURCE[0]}")/v41_cdn_files.sh"

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
raw="https://raw.githubusercontent.com/$GITHUB_REPOSITORY/$CDN_SHA"
cdn="https://cdn.jsdelivr.net/gh/$GITHUB_REPOSITORY@cdn"
fetch() {
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 8 --max-time 20 --max-filesize 8388608 --output "$2" "$1"
}
verify_bytes() {
  local url="$1" expected="$2" out="$3" delay
  for delay in 0 5 12; do
    if (( delay )); then sleep "$delay"; fi
    if fetch "$url" "$out" && cmp -s "$expected" "$out"; then
      return 0
    fi
  done
  return 1
}

for file in "${V41_CDN_FILES[@]}"; do
  if ! verify_bytes "$raw/$file" "$file" "$tmp/$file"; then
    echo "::error::Pinned CDN branch commit bytes not confirmed after retries: $file"
    exit 1
  fi
done

failed=()
for file in "${V41_CDN_FILES[@]}"; do
  if verify_bytes "$cdn/$file" "$file" "$tmp/cdn-$file"; then
    echo "jsDelivr serving verified bytes: $file"
  else
    failed+=("$file")
    echo "::warning::jsDelivr bytes not confirmed: $file. Use GitHub Release."
  fi
done
if (( ${#failed[@]} )); then
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    printf 'jsDelivr read-back not confirmed: %s\n' "${failed[*]}" >> "$GITHUB_STEP_SUMMARY"
  fi
  exit 1
fi
