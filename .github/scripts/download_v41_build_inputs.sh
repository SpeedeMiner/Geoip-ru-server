#!/usr/bin/env bash
set -euo pipefail

# Versioned source data is reviewed in Git rather than duplicated inside YAML.
cp .github/data/geoip_RU_company_asns.tsv "$COMPANY_ASN_REGISTRY"
cp .github/data/geoip_RU_company_asn_policy.tsv "$COMPANY_ASN_POLICY"
test -s "$COMPANY_ASN_REGISTRY"
test -s "$COMPANY_ASN_POLICY"
echo "Company ASN registry entries: $(grep -c '^AS' "$COMPANY_ASN_REGISTRY")"
echo "CORE/SHARED policy rows: $(grep -c '^AS' "$COMPANY_ASN_POLICY")"
sha256sum "$COMPANY_ASN_REGISTRY" "$COMPANY_ASN_POLICY" > geoip_RU_company_asn_registry.sha256sum

# Record the exact mirror selected by the build and the bytes consumed.
# This is per-run provenance, not a claim that mutable upstream refs are immutable.
printf 'SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n' > "$INPUT_PROVENANCE"

record_source_download() {
  local label="$1" output="$2" url="$3" status="$4"
  local digest="-" bytes="0"
  if [[ "$status" == "downloaded" ]]; then
    digest="$(sha256sum "$output" | awk '{print $1}')"
    bytes="$(wc -c < "$output" | tr -d ' ')"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$label" "$(basename "$output")" "$url" "$digest" "$bytes" "$status" >> "$INPUT_PROVENANCE"
}

download_file() {
  local label="$1"
  local output="$2"
  shift 2
  local tmp="${output}.part"
  local url
  rm -f "$tmp"

  for url in "$@"; do
    echo "::group::${label}"
    echo "Trying: ${url}"
    if curl --fail --location --silent --show-error \
      --proto "=https" --proto-redir "=https" --max-filesize 67108864 \
      --connect-timeout 20 --max-time 180 \
      --retry 4 --retry-all-errors --retry-delay 3 --retry-max-time 240 \
      --output "$tmp" "$url"; then
      if [[ -s "$tmp" ]]; then
        mv "$tmp" "$output"
        record_source_download "$label" "$output" "$url" "downloaded"
        echo "Downloaded ${label}: $(wc -c < "$output") bytes"
        echo "::endgroup::"
        return 0
      fi
      echo "Empty response from ${url}"
    else
      echo "Download failed from ${url}"
    fi
    rm -f "$tmp"
    echo "Trying next mirror..."
    echo "::endgroup::"
  done

  echo "::error::Unable to download required source: ${label}"
  return 1
}

download_optional_file() {
  local label="$1" output="$2" url="$3" tmp="${2}.part"
  rm -f "$tmp"
  if curl --fail --location --silent --show-error --proto "=https" --proto-redir "=https" --max-filesize 67108864 --connect-timeout 20 --max-time 180 \
       --retry 2 --retry-all-errors --retry-delay 2 --output "$tmp" "$url" && [[ -s "$tmp" ]]; then
    mv "$tmp" "$output"
    record_source_download "$label" "$output" "$url" "downloaded"
    echo "Downloaded optional ${label}: $(wc -c < "$output") bytes"
  else
    rm -f "$tmp"
    printf '# Optional source unavailable during this build: %s\n' "$url" > "$output"
    record_source_download "$label" "$output" "$url" "unavailable"
    echo "::warning::Optional source unavailable: ${label}; see blocked-source stats for fallback status."
  fi
}

# Static routing inputs have independently reviewed hashes and bounded sizes.
# Never substitute a proxy, mutable ref or self-reported digest on failure.
python3 .github/scripts/download_v41_locked_sources.py \
  --lock .github/data/v41-source-lock.json --provenance "$INPUT_PROVENANCE"

echo "==============================================="
echo "Downloading additive RU ASN/BGP data"
echo "==============================================="

# RIPEstat's Country Resource List is itself derived from RIR delegated
# statistics. Avoid making the RIPEstat API a single point of failure:
# fetch each RIR's authoritative daily file, with cross-RIR mirrors.
echo "==============================================="
echo "Downloading five RIR delegated statistics files"
echo "==============================================="

download_file "AFRINIC DELEGATED STATS" "$AFRINIC_STATS" \
  "https://ftp.afrinic.net/pub/stats/afrinic/delegated-afrinic-latest" \
  "https://ftp.apnic.net/pub/stats/afrinic/delegated-afrinic-latest" \
  "https://ftp.ripe.net/pub/stats/afrinic/delegated-afrinic-latest"

download_file "APNIC DELEGATED STATS" "$APNIC_STATS" \
  "https://ftp.apnic.net/pub/stats/apnic/delegated-apnic-latest" \
  "https://ftp.ripe.net/pub/stats/apnic/delegated-apnic-latest" \
  "https://ftp.afrinic.net/pub/stats/apnic/delegated-apnic-latest"

download_file "ARIN DELEGATED STATS" "$ARIN_STATS" \
  "https://ftp.arin.net/pub/stats/arin/delegated-arin-extended-latest" \
  "https://ftp.arin.net/pub/stats/arin/delegated-arin-latest" \
  "https://ftp.ripe.net/pub/stats/arin/delegated-arin-extended-latest" \
  "https://ftp.apnic.net/pub/stats/arin/delegated-arin-extended-latest"

download_file "LACNIC DELEGATED STATS" "$LACNIC_STATS" \
  "https://ftp.lacnic.net/pub/stats/lacnic/delegated-lacnic-latest" \
  "https://ftp.ripe.net/pub/stats/lacnic/delegated-lacnic-latest" \
  "https://ftp.apnic.net/pub/stats/lacnic/delegated-lacnic-latest"

download_file "RIPE NCC DELEGATED STATS" "$RIPENCC_STATS" \
  "https://ftp.ripe.net/pub/stats/ripencc/delegated-ripencc-latest" \
  "https://ftp.apnic.net/pub/stats/ripencc/delegated-ripencc-latest" \
  "https://ftp.afrinic.net/pub/stats/ripencc/delegated-ripencc-latest"

# Official IANA Special-Purpose registries. IANA currently publishes the CSV
# download under the numbered filename *-1.csv (not the registry-name.csv URL).
# Non-globally-reachable entries
# are included in PRIVATE; globally-reachable exceptions are subtracted back
# out so broad special-purpose blocks do not swallow explicit exceptions.
download_file "IANA IPV4 SPECIAL REGISTRY" "$IANA_V4_CSV" \
  "https://www.iana.org/assignments/iana-ipv4-special-registry/iana-ipv4-special-registry-1.csv"
download_file "IANA IPV6 SPECIAL REGISTRY" "$IANA_V6_CSV" \
  "https://www.iana.org/assignments/iana-ipv6-special-registry/iana-ipv6-special-registry-1.csv"

# Extract RU-registered ASNs AND RU-registered IPv4/IPv6 resources from
# the five authoritative RIR delegated-stat snapshots. IP registration
# country is a corroborating registry signal, not proof of server location.
python3 .github/scripts/build_v41_rir_legacy_inventory.py "$AFRINIC_STATS" "$APNIC_STATS" "$ARIN_STATS" \
  "$LACNIC_STATS" "$RIPENCC_STATS" "$RU_ASN_REGISTRY" \
  "$RIR_PREFIX_INPUT" "$RIR_STATS" "$BY_KZ_ASN_REGISTRY"

# v41 separately inventories the full RU+BY+KZ public address-resource
# set. Registration is DIRECT evidence here, not a physical-geolocation claim.
python3 .github/scripts/build_rir_rukzby_prefixes.py \
  --afrinic "$AFRINIC_STATS" --apnic "$APNIC_STATS" --arin "$ARIN_STATS" \
  --lacnic "$LACNIC_STATS" --ripencc "$RIPENCC_STATS" \
  --output "$RIR_RUKZBY_PREFIX_INPUT" --stats "$RIR_RUKZBY_STATS"

# Convert the official IANA registries into exact non-globally-reachable
# prefixes and explicit globally-reachable exceptions.
python3 .github/scripts/build_v41_iana_special_prefixes.py "$IANA_V4_CSV" "$IANA_V6_CSV" \
  "$IANA_PRIVATE_PREFIX_INPUT" "$IANA_REACHABLE_PREFIX_INPUT"

download_file "IPVERSE ASN/BGP ARCHIVE" "$IPVERSE_BGP_ARCHIVE" \
  "https://codeload.github.com/ipverse/as-ip-blocks/tar.gz/refs/heads/master" \
  "https://github.com/ipverse/as-ip-blocks/releases/latest/download/as-ip-blocks.tar.gz"

# Import RunetFreedom's source categories as separate feeds; do NOT use
# geoip-ru-only.dat because it also contains PRIVATE and ru-whitelist.
# ip.lst and ipresolve.lst are host-IP lists; subnet.lst is explicit RKN-derived CIDR.
download_file "ANTIFILTER EXACT BLOCKED IP LIST" "$BLOCKED_IP_RAW_INPUT" \
  "https://antifilter.download/list/ip.lst"
download_optional_file "ANTIFILTER IPRESOLVE LIST" "$BLOCKED_IPRESOLVE_INPUT" \
  "https://antifilter.download/list/ipresolve.lst"

# Preserve the previously approved blocked-set if ipresolve is empty.
# The baseline is pinned to the exact v38 release commit and SHA-256.
download_file "PINNED V38 APPROVED BLOCKED BASELINE" "$BLOCKED_BASELINE_INPUT" \
  "https://raw.githubusercontent.com/SpeedeMiner/Geoip-ru-server/3033248ea54cb298bafded25ddcd2805d5f0e7ac/geoip_RU_v38_blocked_ip_exclusions.txt"
echo "df909b12b985b23080075821cedc5e2f73b7b1f89abcd9950293b400ce1e4a5d  $BLOCKED_BASELINE_INPUT" | sha256sum -c -
# Historical v38 raw feed snapshots are immutable release assets.
# Restore *only* proven resolver-derived baseline entries. An unknown
# old baseline entry retains its hard/exact status.
download_file "PINNED V38 EXACT IP SOURCE" "$V38_PINNED_IP_INPUT" \
  "https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v38/antifilter-ip.lst"
echo "c9c0656d0188f4afa740d71332b618d42b5606ab27e7561790f47b588781d1cb  $V38_PINNED_IP_INPUT" | sha256sum -c -
download_file "PINNED V38 RESOLVER SOURCE" "$V38_PINNED_IPRESOLVE_INPUT" \
  "https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v38/antifilter-ipresolve.lst"
echo "8d8d11605a299da96006df6303a90b08b4ae25d35c1d1a199708cb83f84cdf44  $V38_PINNED_IPRESOLVE_INPUT" | sha256sum -c -
download_file "PINNED V38 SUBNET SOURCE" "$V38_PINNED_SUBNET_INPUT" \
  "https://github.com/SpeedeMiner/Geoip-ru-server/releases/download/latest-geoip-client-v38/antifilter-subnet.lst"
echo "2554552742bc0da516a321db66b36fa6cece28c4b3c64b66ff6d12320b33bdb6  $V38_PINNED_SUBNET_INPUT" | sha256sum -c -
download_file "ANTIFILTER SUBNET LIST" "$BLOCKED_SUBNET_INPUT" \
  "https://antifilter.download/list/subnet.lst"
# Officially described by the aggregator as /24 summarization of individual
# RKN-derived IPs. The v41 builder applies it separately and reports its
# wider shared-hosting/CDN collateral risk instead of hiding it in subnet.lst.
download_file "ANTIFILTER IPSUM IPV4 /24 SUMMARY" "$BLOCKED_IPSUM_INPUT" \
  "https://antifilter.download/list/ipsum.lst"

# Community and Re-filter are intentionally review-only. They must never
# be silently promoted into automatic DIRECT exclusions.
download_optional_file "ANTIFILTER COMMUNITY CANDIDATES" "$BLOCKED_COMMUNITY_INPUT" \
  "https://community.antifilter.download/list/community.lst"
download_optional_file "RE-FILTER CANDIDATES" "$BLOCKED_REFILTER_INPUT" \
  "https://raw.githubusercontent.com/1andrevich/Re-filter-lists/refs/heads/main/ipsum.lst"

sha256sum "$INPUT_PROVENANCE" > "$INPUT_PROVENANCE_SHA"
sha256sum -c "$INPUT_PROVENANCE_SHA"

# Validate every required core source and the additive ASN/BGP inputs before parsing.
for file in "$HYDRA_INPUT" "$GRIMBIRD_INPUT" "$DIGNE_INPUT" "$DAVOYAN_INPUT" \
            "$GOLUKON_INPUT" "$V2FLY_INPUT" "$V2FLY_SHA_INPUT" \
            "$LOYALSOLDIER_RU_INPUT" "$LOYALSOLDIER_BY_INPUT" "$LOYALSOLDIER_PRIVATE_INPUT" \
            "$BY_KZ_ASN_REGISTRY" "$BLOCKED_IP_RAW_INPUT" "$BLOCKED_BASELINE_INPUT" \
            "$BLOCKED_IPRESOLVE_INPUT" "$BLOCKED_SUBNET_INPUT" "$BLOCKED_IPSUM_INPUT" "$HXEHEX_INPUT" "$W1ZARDZ_INPUT" \
            "$KY_STANDARD_V4_INPUT" "$KY_STANDARD_V6_INPUT" "$KY_SERVICES_INPUT" "$HXEHEX_IP_INPUT" "$ESCAPINGWORM_OPERATOR_INPUT" \
            "$RIR_RUKZBY_PREFIX_INPUT" "$RIR_RUKZBY_STATS" "$AFRINIC_STATS" "$APNIC_STATS" \
            "$ARIN_STATS" "$LACNIC_STATS" "$RIPENCC_STATS" "$RU_ASN_REGISTRY" \
            "$IPVERSE_BGP_ARCHIVE" "$IANA_V4_CSV" "$IANA_V6_CSV"; do
  test -s "$file" || { echo "::error::Missing or empty required input: $file"; exit 1; }
done
test "$(wc -c < "$IPVERSE_BGP_ARCHIVE")" -gt 5000000
gzip -t "$IPVERSE_BGP_ARCHIVE"
for file in "$HYDRA_INPUT" "$GRIMBIRD_INPUT" "$DIGNE_INPUT" "$DAVOYAN_INPUT" "$KIRILL_INPUT" "$GOLUKON_INPUT" "$V2FLY_INPUT" "$LOYALSOLDIER_RU_INPUT" "$LOYALSOLDIER_BY_INPUT" "$LOYALSOLDIER_PRIVATE_INPUT"; do
  test "$(wc -c < "$file")" -gt 100 || { echo "::error::Unexpectedly small GeoIP source: $file"; exit 1; }
done
ls -lh "$HYDRA_INPUT" "$GRIMBIRD_INPUT" "$DIGNE_INPUT" "$DAVOYAN_INPUT" "$KIRILL_INPUT" \
       "$GOLUKON_INPUT" "$V2FLY_INPUT" "$V2FLY_SHA_INPUT" \
       "$LOYALSOLDIER_RU_INPUT" "$LOYALSOLDIER_BY_INPUT" "$LOYALSOLDIER_PRIVATE_INPUT" \
       "$HXEHEX_INPUT" "$W1ZARDZ_INPUT" "$AFRINIC_STATS" "$APNIC_STATS" \
       "$ARIN_STATS" "$LACNIC_STATS" "$RIPENCC_STATS" "$RU_ASN_REGISTRY" "$IPVERSE_BGP_ARCHIVE" \
       "$IANA_V4_CSV" "$IANA_V6_CSV" "$BLOCKED_IP_RAW_INPUT" "$BLOCKED_IPRESOLVE_INPUT" \
       "$BLOCKED_SUBNET_INPUT" "$BLOCKED_COMMUNITY_INPUT" "$BLOCKED_REFILTER_INPUT"
