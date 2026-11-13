import collections
import datetime
import ipaddress
import json
import pathlib
import sys
import tarfile


def read_rir_asns(path, label, minimum=25):
    result = set()
    with open(path, encoding="utf-8") as source:
        for raw in source:
            value = raw.strip().upper()
            if not value or value.startswith("#"):
                continue
            try:
                asn = int(value.removeprefix("AS"))
            except ValueError:
                raise SystemExit(f"Invalid ASN in RIR registry {path}: {raw.rstrip()!r}")
            if not 0 < asn <= 4294967295:
                raise SystemExit(f"ASN outside valid range in {path}: {raw.rstrip()!r}")
            result.add(asn)
    if len(result) < minimum:
        raise SystemExit(f"RIR ASN sanity check failed: only {len(result)} {label} ASNs")
    return result


def read_company_asns(path):
    # TSV format: ASN<TAB>COMPANY_GROUP<TAB>LEGAL_ENTITY_OR_NOTE<TAB>EVIDENCE_URL
    result = {}
    line_count = 0
    with open(path, encoding="utf-8") as source:
        for number, raw in enumerate(source, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = [part.strip() for part in raw.rstrip("\r\n").split("\t")]
            if len(fields) != 4 or not all(fields):
                raise SystemExit(
                    f"Malformed company ASN registry line {number}; expected 4 non-empty TSV fields: {raw.rstrip()!r}"
                )
            try:
                asn = int(fields[0].upper().removeprefix("AS"))
            except ValueError:
                raise SystemExit(f"Invalid company ASN on line {number}: {fields[0]!r}")
            if not 0 < asn <= 4294967295:
                raise SystemExit(f"Company ASN outside valid range on line {number}: {asn}")
            row = {"group": fields[1], "entity": fields[2], "evidence": fields[3]}
            if asn in result and result[asn] != row:
                raise SystemExit(f"Conflicting company ownership entries for AS{asn}")
            result[asn] = row
            line_count += 1
    if line_count < 10:
        raise SystemExit(f"Company ASN allowlist unexpectedly small: only {line_count} entries")
    return result


def is_selected_asn(asn, rir_ru_asns, rir_by_kz_asns, company_asns):
    # Country metadata is not an inclusion filter for selected RU/BY/KZ regional ASNs or affiliates.
    return asn in rir_ru_asns or asn in rir_by_kz_asns or asn in company_asns


def parse_announced_prefixes(prefixes):
    parsed = []
    invalid = 0
    for family, version in (("ipv4", 4), ("ipv6", 6)):
        for raw_prefix in prefixes.get(family, []) or []:
            try:
                network = ipaddress.ip_network(str(raw_prefix), strict=True)
                if network.version != version or network.prefixlen == 0:
                    invalid += 1
                    continue
            except ValueError:
                invalid += 1
                continue
            parsed.append((family, network))
    return parsed, invalid


def add_static_prefix_overrides(prefix_origins, overrides):
    """Add explicit project-approved prefixes without claiming a fresh BGP observation."""
    added = set()
    for raw_prefix, raw_asn in overrides.items():
        network = ipaddress.ip_network(raw_prefix, strict=True)
        asn = int(raw_asn)
        if not 0 < asn <= 4294967295:
            raise SystemExit(f"Invalid ASN for static prefix override {raw_prefix}: {raw_asn}")
        normalized = str(network)
        prefix_origins.setdefault(normalized, set()).add(asn)
        added.add(normalized)
    return added


def self_test_selection():
    rir_ru = {12389}
    rir_by_kz = {25106, 207304}
    companies = {
        208795: {"group": "Yandex", "entity": "Yandex Cloud Kazakhstan LLP", "evidence": "test"},
        212066: {"group": "Yandex", "entity": "Buyuk Reklam Cozumleri LLC (Yandex Turkey)", "evidence": "test"},
    }
    # RU, BY/KZ RIR and a foreign-country company affiliate must all be selected.
    assert is_selected_asn(208795, rir_ru, rir_by_kz, companies)
    assert is_selected_asn(25106, rir_ru, rir_by_kz, companies)
    assert is_selected_asn(207304, rir_ru, rir_by_kz, companies)
    assert is_selected_asn(212066, rir_ru, rir_by_kz, companies)
    sample, invalid = parse_announced_prefixes({
        "ipv4": ["198.51.100.0/24"],
        "ipv6": ["2001:db8:100::/48"],
    })
    assert invalid == 0 and len(sample) == 2
    # A RIR-RU ASN is still selected even if its ASN metadata says a different country.
    assert is_selected_asn(12389, rir_ru, rir_by_kz, companies)
    # A foreign, unlisted ASN is not selected just because it appears in a non-RU country.
    assert not is_selected_asn(64500, rir_ru, rir_by_kz, companies)
    pinned = {}
    pinned_prefixes = add_static_prefix_overrides(pinned, {"45.148.65.0/24": 212066, "2a14:48c6::/48": 212066})
    assert pinned_prefixes == {"45.148.65.0/24", "2a14:48c6::/48"}
    assert pinned["45.148.65.0/24"] == {212066}
    assert pinned["2a14:48c6::/48"] == {212066}


if len(sys.argv) == 4 and sys.argv[1] == "--self-test":
    self_test_selection()
    parsed_company_asns = read_company_asns(sys.argv[2])
    parsed_by_kz_asns = read_rir_asns(sys.argv[3], "BY/KZ")
    if 208795 not in parsed_company_asns or 13238 not in parsed_company_asns:
        raise SystemExit("Company ASN registry self-test failed: Yandex/RU affiliate entries missing")
    if 207304 not in parsed_company_asns or 212066 not in parsed_company_asns:
        raise SystemExit("Company ASN registry self-test failed: Yandex Kazakhstan/Turkey origin entries missing")
    if not is_selected_asn(208795, set(), parsed_by_kz_asns, parsed_company_asns):
        raise SystemExit("Company ASN registry self-test failed: non-RU Yandex ASN not selected")
    if not is_selected_asn(212066, set(), parsed_by_kz_asns, parsed_company_asns):
        raise SystemExit("Company ASN registry self-test failed: Yandex Turkey origin ASN not selected")
    if not any(asn in parsed_by_kz_asns for asn in (25106,)):
        raise SystemExit("BY/KZ registry self-test failed: Belarus MTS AS25106 not found")
    print("Company and BY/KZ ASN selection self-test passed; countryCode is audit-only.")
    raise SystemExit(0)

if len(sys.argv) != 10:
    raise SystemExit(
        "usage: extractor <archive> <rir-ru-asns> <rir-by-kz-asns> <company-asns> <regional-prefixes> "
        "<global-prefixes> <asn-manifest> <company-manifest> <stats>"
    )

archive_path, registry_path, by_kz_registry_path, company_registry_path, ru_prefixes_path, global_prefixes_path, manifest_path, company_manifest_path, stats_path = sys.argv[1:10]
registered_ru_asns = read_rir_asns(registry_path, "RU")
registered_by_kz_asns = read_rir_asns(by_kz_registry_path, "BY/KZ")
company_asns = read_company_asns(company_registry_path)

archive_json_files = malformed_json = invalid_prefixes = 0
rir_country_mismatch = collections.Counter()
regional_country_mismatch = collections.Counter()
company_ipverse_countries = collections.Counter()
selected_prefix_origins = collections.defaultdict(set)
rir_prefix_origins = collections.defaultdict(set)
regional_prefix_origins = collections.defaultdict(set)
company_prefix_origins = collections.defaultdict(set)
global_prefixes = set()
active_selected_asns = {}
raw_selected_v4 = raw_selected_v6 = 0
raw_rir_v4 = raw_rir_v6 = 0
raw_company_v4 = raw_company_v6 = 0
raw_global_v4 = raw_global_v6 = 0

try:
    archive = tarfile.open(archive_path, mode="r:gz")
except (tarfile.TarError, OSError) as exc:
    raise SystemExit(f"Invalid ipverse archive: {exc}")

with archive:
    for member in archive:
        if not member.isfile() or not member.name.endswith("aggregated.json"):
            continue
        stream = archive.extractfile(member)
        if stream is None:
            malformed_json += 1
            continue
        try:
            item = json.load(stream)
        except (json.JSONDecodeError, UnicodeDecodeError):
            malformed_json += 1
            continue
        archive_json_files += 1
        try:
            asn = int(item.get("asn"))
        except (TypeError, ValueError):
            continue

        metadata = item.get("metadata") or {}
        prefixes = item.get("prefixes") or {}
        country_code = str(metadata.get("countryCode") or "UNKNOWN").upper()
        is_rir_ru_asn = asn in registered_ru_asns
        is_rir_by_kz_asn = asn in registered_by_kz_asns
        is_company_asn = asn in company_asns
        selected = is_selected_asn(asn, registered_ru_asns, registered_by_kz_asns, company_asns)

        parsed, invalid = parse_announced_prefixes(prefixes)
        invalid_prefixes += invalid
        if selected:
            row = active_selected_asns.setdefault(asn, {
                "company_group": company_asns.get(asn, {}).get("group", "-"),
                "company_entity": company_asns.get(asn, {}).get("entity", "-"),
                "selection_reason": "+".join(
                    reason for reason, present in (("RIR_RU", is_rir_ru_asn), ("RIR_BY_KZ", is_rir_by_kz_asn), ("COMPANY_ALLOWLIST", is_company_asn)) if present
                ),
                "handle": str(metadata.get("handle") or "-").replace("\t", " ").replace("\n", " "),
                "description": str(metadata.get("description") or "-").replace("\t", " ").replace("\n", " "),
                "ipverse_country": country_code,
                "ipv4": 0,
                "ipv6": 0,
            })
            if is_company_asn:
                company_ipverse_countries[country_code] += 1
            if is_rir_ru_asn and country_code != "RU":
                rir_country_mismatch[country_code] += 1
            if is_rir_by_kz_asn and country_code not in {"BY", "KZ"}:
                regional_country_mismatch[country_code] += 1

        for family, network in parsed:
            normalized = str(network)
            global_prefixes.add(normalized)
            if network.version == 4:
                raw_global_v4 += 1
            else:
                raw_global_v6 += 1
            if not selected:
                continue

            selected_prefix_origins[normalized].add(asn)
            row = active_selected_asns[asn]
            row[family] += 1
            if network.version == 4:
                raw_selected_v4 += 1
            else:
                raw_selected_v6 += 1

            if is_rir_ru_asn:
                rir_prefix_origins[normalized].add(asn)
                if network.version == 4:
                    raw_rir_v4 += 1
                else:
                    raw_rir_v6 += 1
            if is_rir_by_kz_asn:
                regional_prefix_origins[normalized].add(asn)
            if is_company_asn:
                company_prefix_origins[normalized].add(asn)
                if network.version == 4:
                    raw_company_v4 += 1
                else:
                    raw_company_v6 += 1

active_selected_asns = {
    asn: row for asn, row in active_selected_asns.items() if row["ipv4"] + row["ipv6"] > 0
}
yandex_turkey_known_prefixes = {"45.148.65.0/24", "2a14:48c6::/48"}
yandex_turkey_observed_prefixes = {
    prefix for prefix, origins in selected_prefix_origins.items() if 212066 in origins
}
# Project-approved Yandex Turkey DIRECT overrides. These survive even if
# the rolling ipverse observation window temporarily omits the routes.
yandex_static_prefixes = add_static_prefix_overrides(
    selected_prefix_origins,
    {"45.148.65.0/24": 212066, "2a14:48c6::/48": 212066},
)
yandex_turkey_selected_prefixes = {
    prefix for prefix, origins in selected_prefix_origins.items() if 212066 in origins
}
missing_yandex_turkey_prefixes = sorted(yandex_turkey_known_prefixes - yandex_turkey_selected_prefixes)
if missing_yandex_turkey_prefixes:
    raise SystemExit(
        "Yandex Turkey static DIRECT override regression: required prefixes were not inserted: "
        + ", ".join(missing_yandex_turkey_prefixes)
    )
if archive_json_files < 10000:
    raise SystemExit(f"ipverse sanity check failed: only {archive_json_files} aggregated.json files")
if malformed_json:
    raise SystemExit(f"ipverse archive contains {malformed_json} malformed JSON files; refusing partial data")
if len(active_selected_asns) < 25 or not selected_prefix_origins:
    raise SystemExit(
        f"Too few selected ASNs with BGP data: ASNs={len(active_selected_asns)}, prefixes={len(selected_prefix_origins)}"
    )
active_by_kz_count = sum(1 for asn in active_selected_asns if asn in registered_by_kz_asns)
# ipverse is an observation window, so a small active count is possible
# even when the full BY/KZ GeoIP categories are present. Keep this as a
# low failure threshold rather than requiring 20 currently visible ASNs.
if active_by_kz_count < 5:
    raise SystemExit(f"Too few active BY/KZ RIR ASNs with BGP announcements: {active_by_kz_count}")
if len(global_prefixes) < 10000:
    raise SystemExit(f"Global ipverse prefix set unexpectedly small: {len(global_prefixes)}")


def sort_key(value):
    network = ipaddress.ip_network(value)
    return network.version, int(network.network_address), network.prefixlen

with open(ru_prefixes_path, "w", encoding="utf-8") as output:
    output.write(
        "# DIRECT prefixes selected from RIR-RU/BY/KZ or curated company BGP origins, plus explicit static Yandex DIRECT overrides.\n"
    )
    output.write(
        "# ipverse countryCode is audit-only. [STATIC-DIRECT] marks a project-approved prefix pinned independently of the rolling BGP observation window.\n"
    )
    for prefix in sorted(selected_prefix_origins, key=sort_key):
        origins = []
        for asn in sorted(selected_prefix_origins[prefix]):
            labels = []
            if asn in registered_ru_asns:
                labels.append("RIR-RU")
            if asn in registered_by_kz_asns:
                labels.append("RIR-BY/KZ")
            if asn in company_asns:
                labels.append(company_asns[asn]["group"].replace(" ", "_"))
            origin_label = f"AS{asn}[{'+'.join(labels)}]"
            if prefix in yandex_static_prefixes and asn == 212066:
                origin_label += "[STATIC-DIRECT]"
            origins.append(origin_label)
        output.write(f"{prefix} # {','.join(origins)}\n")

with open(global_prefixes_path, "w", encoding="utf-8") as output:
    output.write("# Union of prefixes in ipverse/as-ip-blocks aggregated.json files\n")
    output.write("# Observation window is up to 90 days; absence here is NOT proof of global unroutability.\n")
    for prefix in sorted(global_prefixes, key=sort_key):
        output.write(prefix + "\n")

with open(manifest_path, "w", encoding="utf-8") as output:
    output.write(
        "ASN\tCOMPANY_GROUP\tLEGAL_ENTITY\tINCLUSION_BASIS\tHANDLE\tDESCRIPTION\tIPVERSE_COUNTRY_CODE\tIPV4_PREFIXES\tIPV6_PREFIXES\n"
    )
    for asn in sorted(active_selected_asns):
        row = active_selected_asns[asn]
        output.write(
            f"AS{asn}\t{row['company_group']}\t{row['company_entity']}\t{row['selection_reason']}\t"
            f"{row['handle']}\t{row['description']}\t{row['ipverse_country']}\t{row['ipv4']}\t{row['ipv6']}\n"
        )

with open(company_manifest_path, "w", encoding="utf-8") as output:
    output.write(
        "ASN\tCOMPANY_GROUP\tLEGAL_ENTITY_OR_NOTE\tEVIDENCE\tACTIVE_IN_IPVERSE\tIPVERSE_COUNTRY_CODE\tIPV4_PREFIXES\tIPV6_PREFIXES\tALSO_RIR_RU\tALSO_RIR_BY_KZ\n"
    )
    for asn in sorted(company_asns):
        company = company_asns[asn]
        row = active_selected_asns.get(asn)
        output.write(
            f"AS{asn}\t{company['group']}\t{company['entity']}\t{company['evidence']}\t"
            f"{'yes' if row else 'no'}\t{row['ipverse_country'] if row else '-'}\t"
            f"{row['ipv4'] if row else 0}\t{row['ipv6'] if row else 0}\t"
            f"{'yes' if asn in registered_ru_asns else 'no'}\t"
            f"{'yes' if asn in registered_by_kz_asns else 'no'}\n"
        )

stats = [
    f"Generated UTC: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
    f"ipverse aggregated.json files: {archive_json_files}",
    f"RIR delegated-stats registered RU ASNs: {len(registered_ru_asns)}",
    f"RIR delegated-stats registered BY/KZ ASNs: {len(registered_by_kz_asns)}",
    f"Curated Russian-company ASN allowlist entries: {len(company_asns)}",
    f"Curated company ASNs with ipverse BGP data: {sum(1 for asn in active_selected_asns if asn in company_asns)}",
    f"Selected RIR-RU/BY/KZ or company ASNs with ipverse BGP data: {len(active_selected_asns)}",
    f"Active BY/KZ RIR ASNs with ipverse announcements: {active_by_kz_count}",
    f"Unique prefixes originated by RIR-RU ASNs: {len(rir_prefix_origins)}",
    f"Unique prefixes originated by RIR-BY/KZ ASNs: {len(regional_prefix_origins)}",
    f"Unique prefixes originated by curated Russian-company/affiliate ASNs: {len(company_prefix_origins)}",
    f"Yandex Turkey AS212066 static DIRECT overrides: {', '.join(sorted(yandex_static_prefixes, key=sort_key))}",
    f"Yandex Turkey AS212066 ipverse-observed prefixes at build time: {len(yandex_turkey_known_prefixes & yandex_turkey_observed_prefixes)} of {len(yandex_turkey_known_prefixes)}",
    f"Yandex Turkey AS212066 required DIRECT prefixes covered: {len(yandex_turkey_known_prefixes & yandex_turkey_selected_prefixes)} of {len(yandex_turkey_known_prefixes)}",
    f"Unique prefixes in DIRECT ASN-origin/pinned layer (RIR-RU/BY/KZ OR company allowlist): {len(selected_prefix_origins)}",
    f"Raw selected IPv4 prefix records (RIR-RU OR company allowlist): {raw_selected_v4}",
    f"Raw selected IPv6 prefix records (RIR-RU OR company allowlist): {raw_selected_v6}",
    f"Raw company-allowlisted IPv4 prefix records: {raw_company_v4}",
    f"Raw company-allowlisted IPv6 prefix records: {raw_company_v6}",
    f"Raw RIR-RU IPv4 prefix records: {raw_rir_v4}",
    f"Raw RIR-RU IPv6 prefix records: {raw_rir_v6}",
    f"Unique global ipverse prefixes: {len(global_prefixes)}",
    f"Raw global IPv4 prefix records: {raw_global_v4}",
    f"Raw global IPv6 prefix records: {raw_global_v6}",
    f"Prefixes originated by multiple selected ASNs: {sum(1 for values in selected_prefix_origins.values() if len(values) > 1)}",
    f"Company ASN ipverse countryCode distribution (audit only): " + (", ".join(f"{key}={value}" for key, value in sorted(company_ipverse_countries.items())) or "none"),
    f"RIR-RU ASN ipverse countryCode mismatches (audit only): " + (", ".join(f"{key}={value}" for key, value in sorted(rir_country_mismatch.items())) or "none"),
    f"RIR-BY/KZ ASN ipverse countryCode mismatches (audit only): " + (", ".join(f"{key}={value}" for key, value in sorted(regional_country_mismatch.items())) or "none"),
    f"Invalid/default prefixes skipped: {invalid_prefixes}",
    "Country handling: ipverse countryCode is not used as an inclusion filter for selected RIR-RU, RIR-BY/KZ or company-affiliate origin ASNs.",
    "Scope: announced prefixes present in ipverse aggregated.json observations (up to 90 days), not a real-time or historical-complete RIB.",
    "ASN allowlist semantics: only prefixes originated by the listed ASN are imported; peer/upstream ASNs are not recursively included.",
]
with open(stats_path, "w", encoding="utf-8") as output:
    output.write("\n".join(stats) + "\n")
print("=== RU/BY/KZ RIR and company-affiliate ASN BGP extraction ===")
print("\n".join(stats))
