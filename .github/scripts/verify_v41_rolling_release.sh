#!/usr/bin/env bash
set -euo pipefail
[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
[[ "$SNAPSHOT_SHA" =~ ^[0-9a-f]{40}$ ]]
file=geoip_RU_v41_release_manifest.json
scripts="$(dirname "${BASH_SOURCE[0]}")"
dest="$(mktemp -d)"
trap 'rm -rf -- "$dest"' EXIT

readback() {
  local url="$1" dir="$2" name
  mkdir -p "$dir" || return
  for name in "$file" geoip_RU.dat geoip_RU.dat.sha256sum geoip_RU.srs geoip_RU.srs.sha256sum \
              geoip_PRIVATE.srs geoip_PRIVATE.srs.sha256sum; do
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
      --retry 2 --retry-all-errors --connect-timeout 15 --max-time 45 --max-filesize 8388608 \
      --output "$dir/$name" "$url/$name" || return
  done
  cmp "$file" "$dir/$file" || return
  python3 "$scripts/v41_release_manifest.py" verify "$dir" --manifest "$file" --core-only
}

branch_uri="https://raw.githubusercontent.com/$GITHUB_REPOSITORY/$SNAPSHOT_SHA"
rolling_uri="https://github.com/$GITHUB_REPOSITORY/releases/download/latest-geoip-client-v41"
if [[ "$(git ls-remote --exit-code "https://github.com/$GITHUB_REPOSITORY.git" refs/heads/release | cut -f1)" != "$SNAPSHOT_SHA" ]]; then
  echo "::error::Cannot verify v41 publication: release branch differs from $SNAPSHOT_SHA"
  exit 1
fi
if ! readback "$branch_uri" "$dest/raw"; then
  echo "::error::v41 release commit files differ from the staged candidate: $SNAPSHOT_SHA"
  exit 1
fi
# Rolling assets are mutable and may briefly serve older data. Retry a mismatch
# on a bounded schedule, then surface a partial publish instead of reporting success.
for delay in 0 5 15; do
  if (( delay )); then sleep "$delay"; fi
  if readback "$rolling_uri" "$dest/rolling"; then
    echo "Public rolling DAT/SRS files and checksums match release commit $SNAPSHOT_SHA"
    exit 0
  fi
done
echo "::error::v41 partial publication: release branch is $SNAPSHOT_SHA but rolling files do not match"
exit 1
