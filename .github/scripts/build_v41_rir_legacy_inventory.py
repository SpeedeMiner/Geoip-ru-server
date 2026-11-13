#!/usr/bin/env python3
import datetime
import ipaddress
import pathlib
import sys

inputs = [
    ("afrinic", pathlib.Path(sys.argv[1])),
    ("apnic", pathlib.Path(sys.argv[2])),
    ("arin", pathlib.Path(sys.argv[3])),
    ("lacnic", pathlib.Path(sys.argv[4])),
    ("ripencc", pathlib.Path(sys.argv[5])),
]
asn_output = pathlib.Path(sys.argv[6])
prefix_output = pathlib.Path(sys.argv[7])
stats_output = pathlib.Path(sys.argv[8])
by_kz_asn_output = pathlib.Path(sys.argv[9])
asns_by_country = {"RU": set(), "BY": set(), "KZ": set()}
asns = asns_by_country["RU"]
by_kz_asns = set()
rir_prefixes = set()
rir_v4_prefixes = set()
rir_v6_prefixes = set()
summaries = []
today = datetime.date.today()
raw_asn_records = raw_v4_records = raw_v6_records = 0
generated_v4_cidr_components = generated_v6_cidr_components = 0

def prefix_sort(value):
    net = ipaddress.ip_network(value)
    return net.version, int(net.network_address), net.prefixlen

for expected_registry, path in inputs:
    try:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        raise SystemExit(f"Cannot read {expected_registry} delegated stats: {exc}")
    if not lines:
        raise SystemExit(f"Empty delegated stats file: {path}")

    header = None
    for line in lines:
        normalized = line.lstrip("\ufeff").strip()
        if not normalized or normalized.startswith("#"):
            continue
        fields = [field.strip() for field in normalized.split("|")]
        if (len(fields) >= 7 and (fields[0] == "2" or fields[0].startswith("2."))
                and fields[1].lower() == expected_registry):
            header = fields
            break
    if header is None:
        first_nonempty = next((line.strip() for line in lines if line.strip()), "<empty>")
        raise SystemExit(
            f"Invalid/mismatched {expected_registry} stats header in {path}; "
            f"first non-empty line: {first_nonempty[:160]!r}"
        )

    try:
        snapshot_date = datetime.datetime.strptime(header[5], "%Y%m%d").date()
    except ValueError:
        raise SystemExit(f"Invalid snapshot enddate in {expected_registry}: {header[5]!r}")
    age_days = (today - snapshot_date).days
    if age_days < -1 or age_days > 14:
        raise SystemExit(
            f"Stale/future {expected_registry} delegated stats: {snapshot_date} ({age_days} days old)"
        )

    count_asn = count_v4 = count_v6 = 0
    registry_v4_components = registry_v6_components = 0
    registry_prefixes = set()
    for line in lines:
        normalized = line.lstrip("\ufeff").strip()
        if not normalized or normalized.startswith("#"):
            continue
        fields = [field.strip() for field in normalized.split("|")]
        if len(fields) < 7:
            continue
        registry, country, resource_type, start, value, _date, status = fields[:7]
        country_code = country.upper()
        if registry.lower() != expected_registry or country_code not in {"RU", "BY", "KZ"}:
            continue
        if status.lower() not in {"allocated", "assigned", "legacy"}:
            continue

        kind = resource_type.lower()
        if kind == "asn":
            try:
                first, count = int(start), int(value)
            except ValueError:
                continue
            if first < 1 or count < 1 or first + count - 1 > 4294967295:
                continue
            asns_by_country[country_code].update(range(first, first + count))
            if country_code == "RU":
                count_asn += 1
            continue

        # The RU resource list remains a corroborating input for RU geographic feeds.
        # BY/KZ public address resources are not blindly imported: their GeoIP country
        # categories and observed regional-origin BGP prefixes form the DIRECT layers.
        if country_code != "RU":
            continue

        if kind == "ipv4":
            try:
                first_ip = ipaddress.ip_address(start)
                count = int(value)
                if first_ip.version != 4 or count < 1:
                    continue
                last_int = int(first_ip) + count - 1
                if last_int > (1 << 32) - 1:
                    continue
                last_ip = ipaddress.ip_address(last_int)
                nets = list(ipaddress.summarize_address_range(first_ip, last_ip))
                for net in nets:
                    if net.prefixlen == 0:
                        continue
                    value = str(net)
                    rir_prefixes.add(value)
                    rir_v4_prefixes.add(value)
                    registry_prefixes.add(value)
                    registry_v4_components += 1
                count_v4 += 1
            except (ValueError, TypeError):
                continue
            continue

        if kind == "ipv6":
            try:
                prefixlen = int(value)
                if not 0 < prefixlen <= 128:
                    continue
                net = ipaddress.ip_network(f"{start}/{prefixlen}", strict=True)
                if net.version != 6 or net.prefixlen == 0:
                    continue
                value = str(net)
                rir_prefixes.add(value)
                rir_v6_prefixes.add(value)
                registry_prefixes.add(value)
                registry_v6_components += 1
                count_v6 += 1
            except (ValueError, TypeError):
                continue

    raw_asn_records += count_asn
    raw_v4_records += count_v4
    raw_v6_records += count_v6
    generated_v4_cidr_components += registry_v4_components
    generated_v6_cidr_components += registry_v6_components
    note = " (zero valid for an RIR with no RU records of this type)"
    summaries.append(
        f"{expected_registry}: snapshot={snapshot_date}, ASN records={count_asn}, "
        f"IPv4 resource records={count_v4}, IPv4 CIDR components={registry_v4_components}, "
        f"IPv6 resource records={count_v6}, IPv6 CIDR components={registry_v6_components}, "
        f"registry-local unique CIDRs={len(registry_prefixes)}{note}"
    )
    print(summaries[-1])

by_kz_asns = asns_by_country["BY"] | asns_by_country["KZ"]
if len(asns) < 25 or len(asns) > 100000:
    raise SystemExit(f"RIR ASN registry sanity check failed: {len(asns)} unique RU ASNs")
if len(asns_by_country["BY"]) < 10 or len(asns_by_country["KZ"]) < 10:
    raise SystemExit(
        f"RIR regional ASN inventory is unexpectedly sparse: BY={len(asns_by_country['BY'])}, KZ={len(asns_by_country['KZ'])}"
    )
if len(by_kz_asns) < 25 or len(by_kz_asns) > 100000:
    raise SystemExit(f"RIR BY/KZ ASN registry sanity check failed: {len(by_kz_asns)} unique BY/KZ ASNs")
if not rir_prefixes:
    raise SystemExit("RIR RU IPv4/IPv6 resource inventory is empty; refusing unverified build")

with asn_output.open("w", encoding="utf-8") as handle:
    handle.write("# Unique RU ASNs from allocated, assigned and legacy records in five RIR delegated stats files\n")
    for asn in sorted(asns):
        handle.write(f"AS{asn}\n")

with by_kz_asn_output.open("w", encoding="utf-8") as handle:
    handle.write("# Unique BY/KZ ASNs from allocated, assigned and legacy records in five RIR delegated stats files\n")
    handle.write(f"# BY ASNs: {len(asns_by_country['BY'])}; KZ ASNs: {len(asns_by_country['KZ'])}\n")
    for asn in sorted(by_kz_asns):
        handle.write(f"AS{asn}\n")

with prefix_output.open("w", encoding="utf-8") as handle:
    handle.write("# IPv4/IPv6 resources registered to RU in the five RIR delegated statistics files\n")
    handle.write("# Registration country is not proof of physical server location; used as corroboration only.\n")
    for prefix in sorted(rir_prefixes, key=prefix_sort):
        handle.write(prefix + "\n")

stats_lines = [
    f"Generated UTC: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
    f"Unique RU-registered ASNs: {len(asns)}",
    f"Unique BY-registered ASNs: {len(asns_by_country['BY'])}",
    f"Unique KZ-registered ASNs: {len(asns_by_country['KZ'])}",
    f"Unique BY/KZ-registered ASNs (deduplicated): {len(by_kz_asns)}",
    f"Unique RU-registered IPv4 CIDRs after cross-registry de-duplication: {len(rir_v4_prefixes)}",
    f"Unique RU-registered IPv6 CIDRs after cross-registry de-duplication: {len(rir_v6_prefixes)}",
    f"Unique RU-registered IPv4/IPv6 CIDRs after cross-registry de-duplication: {len(rir_prefixes)}",
    f"Raw IPv4 resource records: {raw_v4_records}",
    f"IPv4 CIDR components emitted before de-duplication: {generated_v4_cidr_components}",
    f"IPv4 CIDR expansion delta (components minus raw records): {generated_v4_cidr_components - raw_v4_records}",
    f"Raw IPv6 resource records: {raw_v6_records}",
    f"IPv6 CIDR components emitted before de-duplication: {generated_v6_cidr_components}",
    f"IPv6 CIDR expansion delta (components minus raw records): {generated_v6_cidr_components - raw_v6_records}",
    f"Raw ASN resource records: {raw_asn_records}",
    "Interpretation: one raw IPv4 resource interval can expand to multiple CIDR components; this is conversion, not contribution from another RIR. Unique output CIDRs are de-duplicated across all registries.",
    "Caveat: RIR country describes registration, not physical hosting location.",
    *summaries,
]
stats_output.write_text("\n".join(stats_lines) + "\n", encoding="utf-8")
print("Unique RU-registered ASNs:", len(asns))
print("Unique RU-registered address prefixes:", len(rir_prefixes))
