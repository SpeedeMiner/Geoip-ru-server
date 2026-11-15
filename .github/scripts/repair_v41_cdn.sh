#!/usr/bin/env bash
set -euo pipefail

if [[ "${GITHUB_REF:-}" != refs/heads/main || "${GITHUB_EVENT_NAME:-}" != workflow_dispatch ]]; then
  echo "::error::CDN repair is available only by manual dispatch on main"
  exit 1
fi
[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$scripts/v41_cdn_files.sh"

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
export GIT_TERMINAL_PROMPT=0
release_ref=refs/heads/release
origin="https://github.com/$GITHUB_REPOSITORY.git"
snapshot="$(git ls-remote --exit-code --refs "$origin" "$release_ref" | cut -f1)"
[[ "$snapshot" =~ ^[0-9a-f]{40}$ ]]
git -C "$tmp" init -q repo
git -C "$tmp/repo" fetch --quiet --no-tags --depth=1 "$origin" "$release_ref"
[[ "$(git -C "$tmp/repo" rev-parse FETCH_HEAD)" == "$snapshot" ]]

mkdir "$tmp/github"
rolling="https://github.com/$GITHUB_REPOSITORY/releases/download/latest-geoip-client-v41"
download() {
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 10 --max-time 25 --retry 1 --retry-max-time 35 \
    --max-filesize "$3" --output "$2" "$rolling/$1"
}
for file in "${V41_CDN_FILES[@]}"; do
  git -C "$tmp/repo" show "$snapshot:$file" > "$tmp/$file"
  [[ -s "$tmp/$file" ]]
  git -C "$tmp/repo" show "$snapshot:$file.sha256sum" > "$tmp/$file.sha256sum"
  digest="$(sha256sum "$tmp/$file" | cut -d' ' -f1)"
  printf '%s  %s\n' "$digest" "$file" | cmp - "$tmp/$file.sha256sum"
  if ! download "$file" "$tmp/github/$file" 8388608 ||
     ! download "$file.sha256sum" "$tmp/github/$file.sha256sum" 512 ||
     ! cmp -s "$tmp/$file" "$tmp/github/$file" ||
     ! cmp -s "$tmp/$file.sha256sum" "$tmp/github/$file.sha256sum"; then
    echo "::error::GitHub rolling release does not match $snapshot for $file. CDN was not updated."
    exit 1
  fi
done

# The publisher resolves and rechecks release and uses a lease for cdn.
# No tag, release ref, GitHub asset, or build is written by this workflow.
(
  cd "$tmp/github"
  SNAPSHOT_SHA="$snapshot" V41_REQUIRE_CDN_READBACK=1 bash "$scripts/deliver_v41_cdn.sh"
)
