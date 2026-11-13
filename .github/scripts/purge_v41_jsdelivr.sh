#!/usr/bin/env bash
set -euo pipefail
purge_jsdelivr() {
  local path="$1"
  local response
  response="$(curl --fail --location --silent --show-error \
    --connect-timeout 15 --max-time 90 \
    "https://purge.jsdelivr.net/gh/${GITHUB_REPOSITORY}@release/${path}")"
  printf '%s\n' "$response"
  python3 -c 'import json,sys; d=json.loads(sys.argv[1]); p=next(iter(d.get("paths",{}).values()),{}); providers=p.get("providers",{}); ok=(d.get("status")=="finished" and p.get("throttled") is False and providers and all(v is True for v in providers.values())); print("Purge status:",d.get("status"),"providers:",providers); sys.exit(0 if ok else 1)' "$response"
}
purge_jsdelivr "geoip_RU.dat"
purge_jsdelivr "geoip_RU.dat.sha256sum"
purge_jsdelivr "geoip_RU_quality_report.txt"
purge_jsdelivr "geoip_RU_v37_additional_provenance.tsv"
purge_jsdelivr "geoip_RU_v41_prefix_provenance.tsv"
purge_jsdelivr "geoip_RU_v41_blocked_provenance.tsv"
purge_jsdelivr "geoip_RU_v41_manifest.json"
purge_jsdelivr "geoip_RU_company_asn_bgp_prefixes.txt"
purge_jsdelivr "geoip_RU_company_asn_core_bgp_prefixes.txt"
purge_jsdelivr "geoip_RU_shared_infrastructure_bgp_prefixes.txt"
purge_jsdelivr "geoip_RU_v41_rir_ru_and_company_origin_prefixes.txt"
purge_jsdelivr "geoip_RU_company_asn_policy.tsv"
purge_jsdelivr "geoip_RU_blocked_ip_exact_and_legacy_hard.txt"
purge_jsdelivr "geoip_RU_blocked_ipresolve_resolver_only.txt"
purge_jsdelivr "geoip_RU_BY_KZ_asn_manifest.txt"
purge_jsdelivr "geoip_RU_input_provenance.tsv"
purge_jsdelivr "geoip_RU_input_provenance.tsv.sha256sum"
purge_jsdelivr "geoip_RU_blocked_ip_exclusions.txt"
