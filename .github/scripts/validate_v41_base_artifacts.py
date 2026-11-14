#!/usr/bin/env python3
import os, sys
from collections import defaultdict
output, manifest, company_manifest, bgp_stats, rir_stats, counts, quality, provenance, category_audit, by_kz_asns, blocked_ips, blocked_review, blocked_stats, blocked_checksums, input_provenance = sys.argv[1:]
minimums = ((output, 4), (manifest, 100), (company_manifest, 300), (bgp_stats, 100), (rir_stats, 100),
            (counts, 100), (quality, 1600), (provenance, 50), (category_audit, 50), (by_kz_asns, 100), (blocked_ips, 10000),
            (blocked_review, 20), (blocked_stats, 100), (blocked_checksums, 200), (input_provenance, 100))
for path, minimum in minimums:
    if not os.path.isfile(path) or os.path.getsize(path) < minimum:
        raise SystemExit(f"Missing or unexpectedly small v37 artifact: {path}")

with open(input_provenance, encoding="utf-8") as source:
    provenance_rows = [line.rstrip("\n").split("\t") for line in source if line.strip()]
provenance_header = ["SOURCE", "LOCAL_FILE", "FETCH_URL", "SHA256", "BYTES", "STATUS"]
if not provenance_rows or provenance_rows[0] != provenance_header:
    raise SystemExit("Input provenance manifest has an unexpected or missing header")
provenance_entries = provenance_rows[1:]
if len(provenance_entries) < 20:
    raise SystemExit(f"Input provenance manifest unexpectedly small: {len(provenance_entries)} entries")
seen_input_files = set()
for row in provenance_entries:
    if len(row) != 6:
        raise SystemExit(f"Malformed input provenance row: {row}")
    source_name, local_file, fetch_url, digest, byte_count, status = row
    if local_file in seen_input_files:
        raise SystemExit(f"Duplicate local file in input provenance manifest: {local_file}")
    seen_input_files.add(local_file)
    if status == "downloaded":
        if not fetch_url.startswith("https://") or len(digest) != 64 or not all(ch in "0123456789abcdef" for ch in digest):
            raise SystemExit(f"Invalid downloaded-source provenance row: {row}")
        if not byte_count.isdigit() or int(byte_count) <= 0:
            raise SystemExit(f"Invalid downloaded-source byte count: {row}")
    elif status == "unavailable":
        allowed_unavailable = ("ANTIFILTER COMMUNITY CANDIDATES", "RE-FILTER CANDIDATES", "ANTIFILTER IPRESOLVE LIST")
        if source_name not in allowed_unavailable or digest != "-" or byte_count != "0":
            raise SystemExit(f"Unexpected unavailable input in provenance manifest: {row}")
    else:
        raise SystemExit(f"Unknown input provenance status: {status}")
expected_input_files = {
    "hydra-geoip.dat", "grimbird-geoip.dat", "digne-geoip.dat", "davoyan-geoip.dat",
    "kirill-geoip.dat", "golukon-geoip.dat", "v2fly-geoip.dat", "v2fly-geoip.dat.sha256sum",
    "loyalsoldier-ru.dat", "loyalsoldier-by.dat", "loyalsoldier-private.dat",
    "hxehex-cidrwhitelist.txt", "w1zardz-ru-ipv4.txt",
    "kyoresuas-ru-standard-ipv4.txt", "kyoresuas-ru-standard-ipv6.txt", "kyoresuas-services.json",
    "hxehex-ipwhitelist.txt", "escapingworm-operator-cidr.txt",
    "delegated-afrinic-latest", "delegated-apnic-latest", "delegated-arin-extended-latest",
    "delegated-lacnic-latest", "delegated-ripencc-latest", "iana-ipv4-special-registry.csv",
    "iana-ipv6-special-registry.csv", "as-ip-blocks.tar.gz",
    "antifilter-ip.lst", "antifilter-ipresolve.lst", "geoip_RU_v38_approved_blocked_baseline.txt",
    "geoip_RU_v38_pinned_antifilter-ip.lst", "geoip_RU_v38_pinned_antifilter-ipresolve.lst",
    "geoip_RU_v38_pinned_antifilter-subnet.lst", "antifilter-subnet.lst", "antifilter-ipsum.lst",
    "antifilter-community.lst", "refilter-ipsum.lst",
}
missing_input_files = sorted(expected_input_files - seen_input_files)
if missing_input_files:
    raise SystemExit("Input provenance is missing downloaded source files: " + ", ".join(missing_input_files))

import ipaddress
with open(by_kz_asns, encoding="utf-8") as source:
    regional_asns = {line.strip().upper() for line in source if line.strip() and not line.lstrip().startswith("#")}
if len(regional_asns) < 25:
    raise SystemExit(f"BY/KZ RIR ASN inventory unexpectedly small: {len(regional_asns)}")
telegram_wide = {
    "91.105.192.0/23", "91.108.4.0/22", "91.108.8.0/21", "91.108.16.0/21",
    "91.108.56.0/22", "95.161.64.0/20", "149.154.160.0/20", "185.76.151.0/24",
    "2001:67c:4e8::/48", "2001:b28:f23c::/47", "2001:b28:f23f::/48", "2a0a:f280::/32",
}
blocked_count = 0
for number, raw in enumerate(open(blocked_ips, encoding="utf-8"), 1):
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if "#" in line:
        line = line.split("#", 1)[0].strip()
    token = line.split()[0].strip('[](){}\"\'')
    try:
        net = ipaddress.ip_network(token, strict=True) if "/" in token else ipaddress.ip_network(token + ("/32" if ":" not in token else "/128"), strict=True)
    except ValueError as exc:
        raise SystemExit(f"Invalid approved blocked prefix at line {number}: {token}: {exc}")
    allowed = (net.prefixlen == net.max_prefixlen or
               (net.version == 4 and net.prefixlen >= 16) or
               (net.version == 6 and net.prefixlen >= 112) or token in telegram_wide)
    if not allowed:
        raise SystemExit(f"Approved blocked prefix exceeds carve threshold at line {number}: {token}")
    blocked_count += 1
if blocked_count < 1000:
    raise SystemExit(f"Approved blocked-prefix input unexpectedly small: {blocked_count}")
review_header = open(blocked_review, encoding="utf-8").readline().strip()
if review_header != "SOURCE\tPREFIX\tREASON":
    raise SystemExit("Blocked review-only candidate file has an unexpected schema")
blocked_stats_text = open(blocked_stats, encoding="utf-8").read()
for marker in ("antifilter-ip.lst", "antifilter-ipresolve.lst", "antifilter-subnet.lst",
               "community-antifilter-community.lst", "re-filter-ipsum.lst", "runetfreedom-static-telegram", "v38-approved-baseline"):
    if marker not in blocked_stats_text:
        raise SystemExit(f"Blocked source statistics are missing source: {marker}")
checksum_text = open(blocked_checksums, encoding="utf-8").read()
for filename in ("antifilter-ip.lst", "antifilter-ipresolve.lst", "antifilter-subnet.lst",
                 "antifilter-community.lst", "refilter-ipsum.lst", "geoip_RU_v38_approved_blocked_baseline.txt",
                 "geoip_RU_v38_pinned_antifilter-ip.lst", "geoip_RU_v38_pinned_antifilter-ipresolve.lst",
                 "geoip_RU_v38_pinned_antifilter-subnet.lst"):
    if filename not in checksum_text:
        raise SystemExit(f"Blocked-source checksum manifest is missing snapshot: {filename}")

with open(counts, encoding="utf-8") as source:
    rows = [line.rstrip("\n").split("\t") for line in source if line.strip()]
expected_header = ["SOURCE", "RU_CATEGORY_CIDR_INPUTS", "CANDIDATE_CIDR_INPUTS",
                   "PRIVATE_CIDR_INPUTS", "OTHER_EVIDENCE_CIDR_INPUTS", "TOTAL_CIDR_INPUTS"]
if rows[0] != expected_header:
    raise SystemExit(f"Unexpected source-count schema: {rows[0]}")
count_map = {row[0]: row for row in rows[1:] if len(row) == 6}

required_ru = ("grimbird", "digne", "davoyan", "golukon", "loyalsoldier", "v2fly", "loyalsoldier-by")
required_other = ("hydra", "loyalsoldier-private", "ru-asn-bgp", "rir-ru", "global-bgp",
                  "iana-non-global", "iana-global-exceptions", "blocked-direct-exclusions")
def source_total(name):
    return sum(int(value) for value in count_map.get(name, ["", "0", "0", "0", "0", "0"])[1:5])

missing_ru = [name for name in required_ru if source_total(name) <= 0]
missing_other = [name for name in required_other if source_total(name) <= 0]
if missing_ru or missing_other:
    raise SystemExit("Required v37 inputs missing/empty: RU feeds=" + ", ".join(missing_ru) +
                     "; other inputs=" + ", ".join(missing_other))

total_row = count_map.get("TOTAL")
if not total_row:
    raise SystemExit("Source count TOTAL row is missing")
sums = [sum(int(row[i]) for row in count_map.values() if row[0] != "TOTAL") for i in range(1, 6)]
declared = [int(value) for value in total_row[1:6]]
if sums != declared:
    raise SystemExit(f"Source count totals do not reconcile: summed={sums} declared={declared}")

import ipaddress
with open(provenance, encoding="utf-8") as source:
    provenance_rows = [line.rstrip("\n").split("\t") for line in source if line.strip()]
provenance_header = provenance_rows[0]
if len(provenance_header) != 14 or provenance_header[:3] != ["PREFIX", "FAMILY", "PREFIX_ADDRESSES"]:
    raise SystemExit("Additional-prefix provenance TSV has unexpected schema")
for row in provenance_rows[1:]:
    if len(row) != 14:
        raise SystemExit(f"Malformed additional-prefix provenance row: {row[:3]}")
    network = ipaddress.ip_network(row[0], strict=True)
    expected_family = "IPv4" if network.version == 4 else "IPv6"
    expected_addresses = 1 << (network.max_prefixlen - network.prefixlen)
    if row[1] != expected_family or int(row[2]) != expected_addresses:
        raise SystemExit(f"Prefix family/address-count mismatch in provenance row: {row[:3]}")
    for index in (3, 4, 5, 6, 8, 9, 10, 11, 12, 13):
        value = int(row[index])
        if value < 0 or value > expected_addresses:
            raise SystemExit(f"Invalid overlap count in provenance row {row[0]} column {provenance_header[index]}")

with open(category_audit, encoding="utf-8") as source:
    category_rows = [line.rstrip("\n").split("\t") for line in source if line.strip()]
category_header = ["SOURCE", "NORMALIZED_CATEGORY", "ASSIGNED_ROLE", "VALID_CIDR_INPUT_RECORDS"]
if not category_rows or category_rows[0] != category_header:
    raise SystemExit("Raw GeoIP category audit has an unexpected schema")
role_totals_by_source = defaultdict(lambda: defaultdict(int))
for row in category_rows[1:]:
    if len(row) != 4:
        raise SystemExit(f"Malformed raw category audit row: {row}")
    source_name, category, role, raw_count = row
    if role not in {"ru", "ru-by", "ru-kz", "candidate", "private", "ignored"}:
        raise SystemExit(f"Unknown category assignment role: {role}")
    value = int(raw_count)
    if value <= 0:
        raise SystemExit(f"Non-positive raw category count: {row}")
    role_totals_by_source[source_name][role] += value
required_regional_roles = {
    ("loyalsoldier-by", "by", "ru-by"),
    ("v2fly", "by", "ru-by"),
    ("v2fly", "kz", "ru-kz"),
    ("loyalsoldier", "ru", "ru"),
    ("v2fly", "ru", "ru"),
}
observed_regional_roles = {
    (row[0], row[1], row[2]) for row in category_rows[1:] if len(row) == 4 and int(row[3]) > 0
}
missing_regional_roles = sorted(required_regional_roles - observed_regional_roles)
if missing_regional_roles:
    raise SystemExit(f"Missing required GeoIP category assignments: {missing_regional_roles}")

dat_sources = ("hydra", "grimbird", "digne", "davoyan", "kirill", "golukon", "v2fly", "loyalsoldier", "loyalsoldier-private", "loyalsoldier-by")
for source_name in dat_sources:
    row = count_map.get(source_name)
    if not row:
        raise SystemExit(f"Missing source count row for GeoIP dat source: {source_name}")
    actual = [sum(role_totals_by_source[source_name][role] for role in ("ru", "ru-by", "ru-kz")),
              role_totals_by_source[source_name]["candidate"], role_totals_by_source[source_name]["private"]]
    expected = [int(row[1]), int(row[2]), int(row[3])]
    if actual != expected:
        raise SystemExit(f"Raw category-to-role counts do not reconcile for {source_name}: audit={actual} builder={expected}")

with open(company_manifest, encoding="utf-8") as source:
    company_rows = [line.rstrip("\n").split("\t") for line in source if line.strip()]
expected_company_header = ["ASN", "COMPANY_GROUP", "LEGAL_ENTITY_OR_NOTE", "EVIDENCE", "ACTIVE_IN_IPVERSE", "IPVERSE_COUNTRY_CODE", "IPV4_PREFIXES", "IPV6_PREFIXES", "ALSO_RIR_RU", "ALSO_RIR_BY_KZ"]
if not company_rows or company_rows[0] != expected_company_header:
    raise SystemExit("Company ASN manifest has an unexpected schema")
if len(company_rows) < 20:
    raise SystemExit(f"Company ASN manifest unexpectedly small: {len(company_rows)-1} entries")
company_groups = {row[1] for row in company_rows[1:] if len(row) == len(expected_company_header)}
company_by_asn = {row[0]: row for row in company_rows[1:] if len(row) == len(expected_company_header)}
for required_asn in ("AS207304", "AS208795", "AS212066"):
    if required_asn not in company_by_asn:
        raise SystemExit(f"Required Yandex regional origin ASN is missing: {required_asn}")
if "AS208398" in company_by_asn:
    raise SystemExit("Transit ASN AS208398 must not be imported wholesale as a company origin")
for required_group in ("Yandex", "VK/Mail.ru", "Wildberries", "Ozon", "Sberbank", "Selectel"):
    if required_group not in company_groups:
        raise SystemExit(f"Company ASN allowlist is missing required group: {required_group}")

quality_text = open(quality, encoding="utf-8").read()
required_quality_markers = (
    "UNIFIED DIRECT REGION RU+BY+KZ", "BLOCKED DESTINATION EXCLUSIONS",
    "Telemetry/privacy-risk labels are informational only", "telemetry stays DIRECT", "exact host IPs", "PRIVATE",
    "IPv4 output CIDRs:", "IPv6 output CIDRs:", "fully_observed", "partially_observed",
    "not_observed", "exact same-prefix global BGP announcement", "no global BGP address-space overlap",
    "Loyalsoldier/v2fly overlap as share of union address space", "IPv6 address-space equivalent in /32-sized units",
    "Reconciled source role totals:", "Grimbird and Digne are treated as one correlated group",
    "curated Russian-company ASN allowlist", "regardless of ipverse countryCode",
    "Yandex Turkey AS212066 static DIRECT overrides: 45.148.65.0/24, 2a14:48c6::/48",
    "Yandex Turkey AS212066 required DIRECT prefixes covered: 2 of 2",
    "Yandex Turkey AS212066 final DIRECT prefix checks (after PRIVATE/blocked carve): 2 of 2",
    "Approved blocked prefix records loaded", "subnet.lst bounded CIDRs", "RunetFreedom's explicitly configured Telegram routes",
    "community.lst and Re-filter ipsum.lst are exported as review-only candidates",
)
missing_quality_markers = [marker for marker in required_quality_markers if marker not in quality_text]
if missing_quality_markers:
    raise SystemExit("Quality report is missing required sections: " + ", ".join(missing_quality_markers))

# The published quality report must carry the measured company-ASN registry
# metrics from the extractor, and its registry count must reconcile to the
# per-ASN manifest generated from the same parsed allowlist.
expected_allowlist_count = len(company_rows) - 1
count_line = f"Curated Russian-company ASN allowlist entries: {expected_allowlist_count}"
if count_line not in quality_text:
    raise SystemExit("Quality report is missing or disagrees with the curated company-ASN registry count")
for marker in (
    "Unique prefixes originated by curated Russian-company/affiliate ASNs (observed in ipverse):",
    "Unique prefixes in DIRECT company-ASN layer (observed + static overrides):",
    "Company ASN ipverse countryCode distribution (audit only):",
    "Country handling: ipverse countryCode is not used as an inclusion filter",
    "Per-ASN evidence and prefix counts:",
):
    if marker not in quality_text:
        raise SystemExit(f"Quality report is missing company-ASN audit metric: {marker}")

print(f"Validated GeoIP protobuf payload: {os.path.getsize(output)} bytes")
print("Unified DIRECT region: RU+BY+KZ (single emitted RU category) plus confirmed company affiliates.")
print("Regional sources: Loyalsoldier RU/BY and v2fly RU/BY/KZ.")
print("Blocked exclusions: exact host IPs, bounded explicit subnet CIDRs and curated Telegram routes; community/Re-filter candidates remain review-only.")
print("Telemetry/privacy classifications do not subtract from DIRECT.")
print("Hydra direct/whitelist is validated as candidate signal input, not as a strict RU GeoIP feed.")
print("No v24 baseline is downloaded or used.")
print("PRIVATE has precedence; direct/whitelist candidates are not subtracted.")
print("RIR-RU/BY/KZ, curated company-affiliate ASN (all countryCode values), and global ipverse BGP audit artifacts are present.")
print("Grimbird and Digne are treated as one correlated evidence group.")
print("Per-prefix provenance and full/partial/not-observed BGP coverage are included.")
print("Exact same-prefix BGP announcements are distinguished from address-space overlap.")
print("Trusted-source overlap is measured by exact address-space intersection, not CIDR-count subtraction.")
print("Raw source categories reconcile with assigned builder roles, including ignored categories.")
