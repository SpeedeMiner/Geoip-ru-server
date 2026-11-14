#!/usr/bin/env bash
set -euo pipefail

snapshot="${SNAPSHOT_VERSION:-}"
if [[ -n "$snapshot" ]]; then
  if [[ "$GITHUB_EVENT_NAME" != workflow_dispatch || ! "$snapshot" =~ ^v41\.(0|[1-9][0-9]{0,5})$ ]]; then
    echo "::error::snapshot_version must be a manual dispatch value such as v41.3"
    exit 1
  fi
else
  [[ "$GITHUB_RUN_ID" =~ ^[0-9]+$ && "$GITHUB_RUN_ATTEMPT" =~ ^[0-9]+$ ]]
  snapshot="geoip-v41-snapshot-${GITHUB_RUN_ID}.${GITHUB_RUN_ATTEMPT}"
fi

source_dir="$(pwd -P)"
dest="$(mktemp -d)"
trap 'rm -rf -- "$dest"' EXIT
git -C "$dest" init
git -C "$dest" remote add origin "https://github.com/${GITHUB_REPOSITORY}.git"
AUTH_B64="$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)"
echo "::add-mask::$AUTH_B64"
auth=(-c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${AUTH_B64}")
git -C "$dest" "${auth[@]}" fetch --depth=1 origin refs/heads/release
[[ "$(git -C "$dest" rev-parse FETCH_HEAD)" == "$PREVIOUS_RELEASE_SHA" ]]
git -C "$dest" checkout -b release FETCH_HEAD
git -C "$dest" rm -r --ignore-unmatch -- .
for file in \
  "$V41_OUTPUT_FILE" "$OUTPUT_SHA_FILE" "$CATEGORY_FILE" "$SOURCE_FILE" \
  "$SOURCE_COUNTS" "$CATEGORY_AUDIT" "$V41_QUALITY_REPORT" "$QUALITY_REPORT" "$V41_METRICS" "$V41_PREFIX_PROVENANCE" "$V41_BLOCKED_PROVENANCE" "$V41_BLOCKED_FILE" "$V41_BLOCKED_SHA" "$V41_MANIFEST" "$PROVENANCE_FILE" "$ASN_MANIFEST" "$COMPANY_ASN_MANIFEST" "$COMPANY_ASN_PREFIXES" "$CORE_COMPANY_PREFIXES" "$SHARED_INFRASTRUCTURE_PREFIXES" "$COMPANY_ASN_POLICY" "$REGIONAL_ORIGIN_PREFIXES" "$COMPANY_ASN_REGISTRY" "geoip_RU_company_asn_registry.sha256sum" "$BLOCKED_IP_EXACT_INPUT" "$BLOCKED_IPRESOLVE_ONLY_INPUT" "$ASN_STATS" \
  "$RU_PREFIX_INPUT" "$RU_ASN_REGISTRY" "$BY_KZ_ASN_REGISTRY" "$RIR_PREFIX_INPUT" "$RIR_STATS" "$RIR_RUKZBY_PREFIX_INPUT" "$RIR_RUKZBY_STATS" "$GLOBAL_BGP_PREFIX_INPUT" \
  "$BLOCKED_IP_INPUT" "$BLOCKED_IP_SHA_FILE" "$BLOCKED_BASELINE_INPUT" "$BLOCKED_REVIEW_INPUT" "$BLOCKED_STATS_INPUT" "$BLOCKED_CHECKSUMS_INPUT" "$INPUT_PROVENANCE" "$INPUT_PROVENANCE_SHA" "$KY_STANDARD_V4_INPUT" "$KY_STANDARD_V6_INPUT" "$KY_SERVICES_INPUT" "$W1ZARDZ_INPUT" "$HXEHEX_IP_INPUT" "$ESCAPINGWORM_OPERATOR_INPUT" "$BLOCKED_IPSUM_INPUT"; do
  cp "$source_dir/$file" "$dest/$(basename "$file")"
done
# The small marker links this exact release tree to its create-only snapshot
# asset. Do not commit the archive into rolling Git history.
printf '%s\n' "$snapshot" > "$dest/geoip_RU_ipverse_snapshot_tag.txt"
git -C "$dest" config user.name "github-actions[bot]"
git -C "$dest" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git -C "$dest" add --all
if ! git -C "$dest" diff --cached --quiet; then
  git -C "$dest" commit -m "Publish GeoIP DIRECT RU+BY+KZ CLIENT v41"
fi
if git -C "$dest" "${auth[@]}" ls-remote --exit-code origin "refs/tags/$snapshot"; then
  echo "::error::Snapshot tag already exists: $snapshot"
  exit 1
else
  status=$?
  [[ "$status" == 2 ]] || exit "$status"
fi
git -C "$dest" tag "$snapshot"
# Publish the snapshot tag only. Moving release must wait for asset readback.
GIT_TERMINAL_PROMPT=0 git -C "$dest" "${auth[@]}" push --atomic origin \
  "refs/tags/$snapshot"
printf 'snapshot=%s\nsnapshot_sha=%s\n' "$snapshot" "$(git -C "$dest" rev-parse HEAD)" >> "$GITHUB_OUTPUT"
