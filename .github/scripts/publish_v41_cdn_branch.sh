#!/usr/bin/env bash
set -euo pipefail

[[ "${GITHUB_REF:-}" == refs/heads/main && "${GITHUB_EVENT_NAME:-}" != pull_request ]]
[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
[[ "$SNAPSHOT_SHA" =~ ^[0-9a-f]{40}$ ]]
source "$(dirname "${BASH_SOURCE[0]}")/v41_cdn_files.sh"

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
export GIT_TERMINAL_PROMPT=0
auth_b64="$(printf 'x-access-token:%s' "${GITHUB_TOKEN:?}" | base64 -w0)"
printf '::add-mask::%s\n' "$auth_b64"
auth=(-c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${auth_b64}")
git -C "$tmp" init -q
git -C "$tmp" remote add origin "https://github.com/${GITHUB_REPOSITORY}.git"
remote_git() { git -C "$tmp" "${auth[@]}" "$@"; }

release_ref=refs/heads/release
cdn_ref=refs/heads/cdn
current_release() {
  remote_git ls-remote --exit-code --refs origin "$release_ref" | cut -f1
}
remote_git fetch --no-tags --depth=1 origin "$release_ref:refs/published/release"
if [[ "$(git -C "$tmp" rev-parse refs/published/release)" != "$SNAPSHOT_SHA" ]]; then
  echo "::error::CDN input is not the promoted release commit"
  exit 1
fi
expected="$(printf '100644 blob %s\n' "${V41_CDN_FILES[@]}" | LC_ALL=C sort)"
legacy="$(printf '100644 blob %s\n' "${V41_LEGACY_CDN_FILES[@]}" | LC_ALL=C sort)"
tree_inventory() {
  # Inspect the root exactly, including directory entries that -r would hide.
  git -C "$tmp" ls-tree --format='%(objectmode) %(objecttype) %(path)' "$@" | LC_ALL=C sort
}
previous=""
parents=()
if remote_git ls-remote --exit-code --refs origin "$cdn_ref" > "$tmp/cdn-remote"; then
  IFS=$'\t' read -r previous ref < "$tmp/cdn-remote"
  [[ "$previous" =~ ^[0-9a-f]{40}$ && "$ref" == "$cdn_ref" ]]
  remote_git fetch --no-tags --depth=1 origin "$cdn_ref:refs/published/cdn"
  [[ "$(git -C "$tmp" rev-parse refs/published/cdn)" == "$previous" ]]
  previous_inventory="$(tree_inventory "$previous")"
  # Accept only the exact old tree for the transition or the exact new tree.
  if [[ "$previous_inventory" != "$expected" && "$previous_inventory" != "$legacy" ]]; then
    echo "::error::Existing cdn branch has unexpected files or modes"
    exit 1
  fi
  parents=(-p "$previous")
else
  [[ "$?" == 2 ]] || exit 1
fi

# Create a new tree from an empty index, not a checkout or a copy of release.
# Validate every checksum and mirror only the RU MRS sidecar.
git -C "$tmp" read-tree --empty
mkdir "$tmp/verify"
for file in "${V41_CLIENT_BINARIES[@]}"; do
  # Require a plain blob and its plain checksum in the checked release tree.
  inventory="$(tree_inventory "$SNAPSHOT_SHA" -- "$file" "$file.sha256sum")"
  [[ "$inventory" == "$(printf '100644 blob %s\n' "$file" "$file.sha256sum")" ]]
  git -C "$tmp" show "$SNAPSHOT_SHA:$file" > "$tmp/verify/$file"
  [[ -s "$tmp/verify/$file" ]]
  git -C "$tmp" show "$SNAPSHOT_SHA:$file.sha256sum" > "$tmp/verify/$file.sha256sum"
  digest="$(sha256sum "$tmp/verify/$file" | cut -d' ' -f1)"
  printf '%s  %s\n' "$digest" "$file" | cmp - "$tmp/verify/$file.sha256sum"
  blob="$(git -C "$tmp" rev-parse "$SNAPSHOT_SHA:$file")"
  git -C "$tmp" update-index --add --cacheinfo "100644,$blob,$file"
  if [[ "$file" == geoip_RU.mrs ]]; then
    blob="$(git -C "$tmp" rev-parse "$SNAPSHOT_SHA:$file.sha256sum")"
    git -C "$tmp" update-index --add --cacheinfo "100644,$blob,$file.sha256sum"
  fi
done
tree="$(git -C "$tmp" write-tree)"
[[ "$(tree_inventory "$tree")" == "$expected" ]]
if [[ -n "$previous" && "$(git -C "$tmp" rev-parse "$previous^{tree}")" == "$tree" ]]; then
  commit="$previous"
  [[ "$(current_release)" == "$SNAPSHOT_SHA" ]]
  [[ "$(remote_git ls-remote --exit-code --refs origin "$cdn_ref" | cut -f1)" == "$previous" ]]
  echo "CDN binaries unchanged at $commit"
else
  commit="$(git -C "$tmp" -c user.name='github-actions[bot]' \
    -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
    commit-tree "$tree" "${parents[@]}" -m "Publish v41 client binaries from release $SNAPSHOT_SHA")"
  [[ "$(current_release)" == "$SNAPSHOT_SHA" ]]
  remote_git push --force-with-lease="$cdn_ref:$previous" origin "$commit:$cdn_ref"
  echo "Published the checked client files to cdn at $commit"
fi
[[ "$(remote_git ls-remote --exit-code --refs origin "$cdn_ref" | cut -f1)" == "$commit" ]]
printf 'cdn_sha=%s\n' "$commit" >> "$GITHUB_OUTPUT"
