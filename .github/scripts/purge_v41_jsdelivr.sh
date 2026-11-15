#!/usr/bin/env bash
set -euo pipefail

[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
source "$(dirname "${BASH_SOURCE[0]}")/v41_cdn_files.sh"

# CDN cache refresh is best effort. Check each response for the requested
# path, and report partial failure only after all compatibility URLs were tried.
purge_jsdelivr() {
  local path="$1"
  local key="/gh/${GITHUB_REPOSITORY:?set GITHUB_REPOSITORY (owner/repo)}@cdn/${path}"
  local response code
  if response="$(curl --fail --location --silent --show-error \
    --proto '=https' --proto-redir '=https' --connect-timeout 10 --max-time 25 \
    "https://purge.jsdelivr.net${key}")"; then
    :
  else
    code=$?
    printf '::warning::jsDelivr purge request failed for %s (curl %s)\n' "$path" "$code"
    return 1
  fi
  if ! python3 -c '
import json, sys
try:
    result = json.load(sys.stdin)
    info = result["paths"][sys.argv[1]]
    providers = info["providers"]
    if (result["status"] != "finished" or info["throttled"] is not False
        or not isinstance(providers, dict) or not providers
        or not all(value is True for value in providers.values())):
        sys.exit(1)
except (KeyError, TypeError, ValueError):
    sys.exit(1)
' "$key" <<< "$response"; then
    printf '::warning::jsDelivr did not confirm purge for %s\n' "$path"
    return 1
  fi
  printf 'jsDelivr purge confirmed: %s\n' "$path"
}


report() {
  local line="$1"
  printf '%s\n' "$line"
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    printf '%s\n' "$line" >> "$GITHUB_STEP_SUMMARY"
  fi
}

failed=()
success=0
for path in "${V41_CDN_FILES[@]}"; do
  if purge_jsdelivr "$path"; then
    success=$((success + 1))
  else
    failed+=("$path")
  fi
done

report ""
report "### jsDelivr cache refresh"
report ""
report "Confirmed: $success/${#V41_CDN_FILES[@]}. Failed: ${#failed[@]}."
if (( ${#failed[@]} )); then
  report ""
  for path in "${failed[@]}"; do
    report "- Unconfirmed: $path"
  done
  report ""
  report "Use the run-specific GitHub Release and its SHA-256 sidecars if a rolling CDN URL is stale."
  exit 1
fi
