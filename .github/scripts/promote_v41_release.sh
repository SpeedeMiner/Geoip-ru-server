#!/usr/bin/env bash
set -euo pipefail

[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
[[ "$SNAPSHOT_TAG" =~ ^(v41\.(0|[1-9][0-9]{0,5})|geoip-v41-snapshot-[0-9]{1,20}\.[0-9]{1,10})$ ]]
[[ "$SNAPSHOT_SHA" =~ ^[0-9a-f]{40}$ && "$PREVIOUS_RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]
verify="$(dirname "${BASH_SOURCE[0]}")/verify_v41_ipverse_archive.py"
dest="$(mktemp -d)"
trap 'rm -rf -- "$dest"' EXIT
AUTH_B64="$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)"
echo "::add-mask::$AUTH_B64"
auth=(-c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${AUTH_B64}")

git -C "$dest" init -q
git -C "$dest" remote add origin "https://github.com/${GITHUB_REPOSITORY}.git"
tag_ref="refs/tags/$SNAPSHOT_TAG"
git -C "$dest" "${auth[@]}" fetch --depth=2 --no-tags origin \
  "refs/heads/release:refs/remotes/origin/release" "$tag_ref:$tag_ref"
[[ "$(git -C "$dest" rev-parse refs/remotes/origin/release)" == "$PREVIOUS_RELEASE_SHA" ]]
[[ "$(git -C "$dest" rev-parse "$tag_ref")" == "$SNAPSHOT_SHA" ]]
# The candidate must be a single direct child of the independently checked tip.
[[ "$(git -C "$dest" rev-list --parents -n 1 "$SNAPSHOT_SHA")" == "$SNAPSHOT_SHA $PREVIOUS_RELEASE_SHA" ]]

git -C "$dest" show "$SNAPSHOT_SHA:geoip_RU_ipverse_snapshot_tag.txt" > "$dest/marker"
git -C "$dest" show "$SNAPSHOT_SHA:geoip_RU_input_provenance.tsv" > "$dest/provenance.tsv"
[[ "$(python3 "$verify" --provenance "$dest/provenance.tsv" --snapshot-tag-file "$dest/marker")" == "$SNAPSHOT_TAG" ]]

# Check the actual published download, not the local candidate or the upstream URL.
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --retry 3 --retry-all-errors --connect-timeout 15 --max-time 90 --max-filesize 67108864 \
  --output "$dest/as-ip-blocks.tar.gz" \
  "https://github.com/$GITHUB_REPOSITORY/releases/download/$SNAPSHOT_TAG/as-ip-blocks.tar.gz"
python3 "$verify" --provenance "$dest/provenance.tsv" --archive "$dest/as-ip-blocks.tar.gz"

# Require the exact checked parent to still be current when the server updates
# the ref. The direct-parent check above guarantees this is a fast-forward.
GIT_TERMINAL_PROMPT=0 git -C "$dest" "${auth[@]}" push \
  --force-with-lease="refs/heads/release:$PREVIOUS_RELEASE_SHA" \
  origin "$SNAPSHOT_SHA:refs/heads/release"
