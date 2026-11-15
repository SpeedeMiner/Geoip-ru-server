#!/usr/bin/env bash
set -euo pipefail

[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
snapshot="${1:?pass the expected release commit}"
output="${2:?pass a clean output directory}"
[[ "$snapshot" =~ ^[0-9a-f]{40}$ && -d "$output" ]]
source "$(dirname -- "${BASH_SOURCE[0]}")/v41_cdn_files.sh"

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
export GIT_TERMINAL_PROMPT=0
release_ref=refs/heads/release
origin="https://github.com/$GITHUB_REPOSITORY.git"
git -C "$tmp" init -q repo
git -C "$tmp/repo" fetch --quiet --no-tags --depth=1 "$origin" "$release_ref"
if [[ "$(git -C "$tmp/repo" rev-parse FETCH_HEAD)" != "$snapshot" ]]; then
  echo "::error::Current release ref is not the expected $snapshot. CDN was not updated."
  exit 1
fi

rolling="https://github.com/$GITHUB_REPOSITORY/releases/download/latest-geoip-client-v41"
download() {
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 10 --max-time 25 --retry 1 --retry-all-errors --retry-max-time 35 \
    --max-filesize "$3" --output "$2" "$rolling/$1"
}
for file in "${V41_CDN_FILES[@]}"; do
  git -C "$tmp/repo" show "$snapshot:$file" > "$tmp/$file"
  [[ -s "$tmp/$file" ]]
  git -C "$tmp/repo" show "$snapshot:$file.sha256sum" > "$tmp/$file.sha256sum"
  digest="$(sha256sum "$tmp/$file" | cut -d' ' -f1)"
  printf '%s  %s\n' "$digest" "$file" | cmp - "$tmp/$file.sha256sum"
  if ! download "$file" "$output/$file" 8388608 ||
     ! download "$file.sha256sum" "$output/$file.sha256sum" 512 ||
     ! cmp -s "$tmp/$file" "$output/$file" ||
     ! cmp -s "$tmp/$file.sha256sum" "$output/$file.sha256sum"; then
    echo "::error::GitHub rolling release does not match $snapshot for $file. CDN was not updated."
    exit 1
  fi
done

echo "GitHub rolling client binaries and checksums match $snapshot"
