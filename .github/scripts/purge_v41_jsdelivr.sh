#!/usr/bin/env bash
set -euo pipefail

# CDN cache refresh is best effort. Check each response for the requested
# path, and report partial failure only after all compatibility URLs were tried.
purge_jsdelivr() {
  local path="$1"
  local key="/gh/${GITHUB_REPOSITORY:?set GITHUB_REPOSITORY (owner/repo)}@release/${path}"
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

paths=(
  geoip_RU.dat geoip_RU.dat.sha256sum
  geoip_RU.srs geoip_RU.srs.sha256sum
  geoip_PRIVATE.srs geoip_PRIVATE.srs.sha256sum
  geoip_RU_quality_report.txt
  geoip_RU_v37_additional_provenance.tsv
  geoip_RU_v41_prefix_provenance.tsv
  geoip_RU_v41_blocked_provenance.tsv
  geoip_RU_v41_manifest.json
  geoip_RU_company_asn_bgp_prefixes.txt
  geoip_RU_company_asn_core_bgp_prefixes.txt
  geoip_RU_shared_infrastructure_bgp_prefixes.txt
  geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt
  geoip_RU_company_asn_policy.tsv
  geoip_RU_blocked_ip_exact_and_legacy_hard.txt
  geoip_RU_blocked_ipresolve_resolver_only.txt
  geoip_RU_BY_KZ_asn_manifest.txt
  geoip_RU_input_provenance.tsv
  geoip_RU_input_provenance.tsv.sha256sum
  geoip_RU_blocked_ip_exclusions.txt
)

report() {
  local line="$1"
  printf '%s\n' "$line"
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    printf '%s\n' "$line" >> "$GITHUB_STEP_SUMMARY"
  fi
}

failed=()
success=0
for path in "${paths[@]}"; do
  if purge_jsdelivr "$path"; then
    success=$((success + 1))
  else
    failed+=("$path")
  fi
done

report ""
report "### jsDelivr cache refresh"
report ""
report "Confirmed: $success/${#paths[@]}. Failed: ${#failed[@]}."
if (( ${#failed[@]} )); then
  report ""
  for path in "${failed[@]}"; do
    report "- Unconfirmed: $path"
  done
  report ""
  report "Use the run-specific GitHub Release and its SHA-256 sidecars if a rolling CDN URL is stale."
  exit 1
fi
