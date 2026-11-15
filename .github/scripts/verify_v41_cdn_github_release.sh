#!/usr/bin/env bash
set -euo pipefail

[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
snapshot="${1:?pass the expected release commit}"
output="${2:?pass a clean output directory}"
fallback_tag="${3:-latest-geoip-client-v41}"
[[ "$fallback_tag" =~ ^(latest-geoip-client-v41|v41\.(0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]{1,20}\.[0-9]{1,10})$ ]]
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

base="https://github.com/$GITHUB_REPOSITORY/releases/download"
rolling="$base/latest-geoip-client-v41"
versioned=""
if [[ "$fallback_tag" != latest-geoip-client-v41 ]]; then
  tag_ref="refs/tags/$fallback_tag"
  if ! git -C "$tmp/repo" show "$snapshot:geoip_RU_ipverse_snapshot_tag.txt" > "$tmp/tag-marker" ||
     ! printf '%s\n' "$fallback_tag" | cmp -s - "$tmp/tag-marker" ||
     ! git -C "$tmp/repo" fetch --quiet --no-tags --depth=1 "$origin" "$tag_ref:$tag_ref" ||
     [[ "$(git -C "$tmp/repo" rev-parse "$tag_ref^{commit}")" != "$snapshot" ]]; then
    echo "::error::GitHub versioned snapshot tag or marker does not match $snapshot. CDN was not updated."
    exit 1
  fi
  versioned="$base/$fallback_tag"
fi
download() {
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 10 --max-time 25 --retry 1 --retry-all-errors --retry-max-time 35 \
    --max-filesize "$3" --output "$2" "$1"
}
for file in "${V41_CDN_FILES[@]}"; do
  git -C "$tmp/repo" show "$snapshot:$file" > "$tmp/$file"
  [[ -s "$tmp/$file" ]]
  git -C "$tmp/repo" show "$snapshot:$file.sha256sum" > "$tmp/$file.sha256sum"
  digest="$(sha256sum "$tmp/$file" | cut -d' ' -f1)"
  printf '%s  %s\n' "$digest" "$file" | cmp - "$tmp/$file.sha256sum"
  if ! download "$rolling/$file" "$output/$file" 8388608 ||
     ! download "$rolling/$file.sha256sum" "$output/$file.sha256sum" 512 ||
     ! cmp -s "$tmp/$file" "$output/$file" ||
     ! cmp -s "$tmp/$file.sha256sum" "$output/$file.sha256sum"; then
    echo "::error::GitHub rolling release does not match $snapshot for $file. CDN was not updated."
    exit 1
  fi
  if [[ -n "$versioned" ]]; then
    if ! download "$versioned/$file" "$tmp/fallback" 8388608 ||
       ! cmp -s "$tmp/$file" "$tmp/fallback" ||
       ! download "$versioned/$file.sha256sum" "$tmp/fallback-checksum" 512 ||
       ! cmp -s "$tmp/$file.sha256sum" "$tmp/fallback-checksum"; then
      echo "::error::GitHub versioned snapshot $fallback_tag does not match $snapshot for $file. CDN was not updated."
      exit 1
    fi
  fi
done

echo "GitHub rolling client binaries and checksums match $snapshot"
if [[ -n "$versioned" ]]; then
  echo "GitHub versioned client binaries and checksums match $snapshot ($fallback_tag)"
fi
