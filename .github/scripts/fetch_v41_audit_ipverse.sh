#!/usr/bin/env bash
# Fetch archive bytes for the already selected release commit, never for a newer ref.
set -euo pipefail

repo="$1"
release_sha="$2"
provenance="$3"
archive="$4"
[[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
[[ "$release_sha" =~ ^[0-9a-f]{40}$ ]]
verify="$(dirname "${BASH_SOURCE[0]}")/verify_v41_ipverse_archive.py"
temporary="$(mktemp -d)"
trap 'rm -rf -- "$temporary"' EXIT

marker="https://raw.githubusercontent.com/$repo/$release_sha/geoip_RU_ipverse_snapshot_tag.txt"
status="$(curl --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --connect-timeout 15 --max-time 60 --max-filesize 256 \
  --retry 2 --output "$temporary/tag" --write-out '%{http_code}' "$marker")"

if [[ "$status" == 200 ]]; then
  tag="$(python3 "$verify" --provenance "$provenance" --snapshot-tag-file "$temporary/tag")"
  url="https://github.com/$repo/releases/download/$tag/as-ip-blocks.tar.gz"
  echo "Using retained ipverse archive from snapshot $tag"
elif [[ "$status" == 404 ]]; then
  # Existing releases predate retention. Their original URL is usable only
  # while it still returns exactly the originally recorded compressed bytes.
  url="$(python3 "$verify" --provenance "$provenance" --source-url)"
  echo '::notice::Legacy release has no retained ipverse archive; upstream bytes must match its recorded SHA-256.'
else
  printf 'Unexpected HTTP status %s while fetching the pinned release snapshot marker\n' "$status" >&2
  exit 1
fi

part="$(mktemp "${archive}.part.XXXXXX")"
trap 'rm -f -- "$part"; rm -rf -- "$temporary"' EXIT
curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
  --connect-timeout 15 --max-time 180 --max-filesize 67108864 \
  --retry 3 --output "$part" "$url"
python3 "$verify" --provenance "$provenance" --archive "$part"
mv -f -- "$part" "$archive"
