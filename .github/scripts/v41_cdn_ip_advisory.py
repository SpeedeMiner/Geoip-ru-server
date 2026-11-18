"""Parse and compare third-party CDN scopes. Never used by routing or publication."""
import ipaddress
import json
import re

from build_v41_overlay import intersect, interval_size, intervals, networks_from_intervals

SOURCE = "cdn-ip-database"
FORMAT = "cdn-ip-database-json"
ROLE = "advisory-no-routing-change"
URL = "https://raw.githubusercontent.com/mansourjabin/cdn-ip-database/main/data/resolved_ips.json"
MAX_BYTES = 2 * 1024 * 1024
MAX_PROVIDERS = 128
MAX_CIDRS = 25_000
PROVIDER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._()+&-]{0,79}")
NETWORK_TEXT = re.compile(r"[0-9A-Fa-f:.]+(?:/[0-9]{1,3})?")


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate CDN database JSON field")
        obj[key] = value
    return obj


def parse_database(payload):
    """Return networks and explicit host-bit normalizations, grouped by provider."""
    data = json.loads(payload, object_pairs_hook=unique_object)
    if not isinstance(data, dict) or not 0 < len(data) <= MAX_PROVIDERS:
        raise ValueError("invalid CDN database root")
    providers = {}
    total = 0
    for name, record in data.items():
        if (not PROVIDER_NAME.fullmatch(name) or name != name.strip()
                or not isinstance(record, dict) or not isinstance(record.get("asns"), list)
                or not isinstance(record.get("ips"), list)):
            raise ValueError("invalid CDN provider record")
        # ASN metadata is deliberately not used to expand any reported scope.
        total += len(record["ips"])
        if total > MAX_CIDRS:
            raise ValueError("CDN database exceeds CIDR limit")
        nets, normalized = set(), {}
        for value in record["ips"]:
            if not isinstance(value, str) or not NETWORK_TEXT.fullmatch(value):
                raise ValueError("invalid CDN database CIDR")
            # Literal IPs supplied without a mask are exact /32 or /128 hosts.
            net = ipaddress.ip_network(value, strict=False)
            if net.prefixlen == 0:
                raise ValueError("default route in CDN database")
            if ipaddress.ip_address(value.split("/")[0]) != net.network_address:
                normalized[value] = str(net)
            nets.add(net)
        providers[name] = (nets, normalized)
    if not any(nets for nets, _ in providers.values()):
        raise ValueError("CDN database contains no usable scopes")
    return providers


def overlap_details(target, networks, family):
    parts = intersect(target, networks)
    return {
        "addresses": str(interval_size(parts)),
        "cidrs": [str(net) for net in sorted(networks_from_intervals(parts, family))],
    }


def provider_scope_index(providers):
    return {
        name: {family: spans for family in (4, 6) if (spans := intervals(nets, family))}
        for name, nets in sorted(providers.items()) if nets
    }


def prefix_overlaps(target, family, provider_index):
    return [
        {"provider": name, **detail}
        for name, scopes in provider_index.items() if family in scopes
        if (detail := overlap_details(target, scopes[family], family))["cidrs"]
    ]


def delta_overlaps(direct_delta, provider_index):
    results = []
    for name, scopes in provider_index.items():
        families = {
            f"ipv{family}": {
                change: overlap_details(target, spans, family)
                for change, target in direct_delta[family].items()
            }
            for family, spans in scopes.items()
        }
        if any(detail["cidrs"] for changes in families.values() for detail in changes.values()):
            results.append({"provider": name, **families})
    return results


def status_line(info):
    if info['status'] != 'AVAILABLE':
        return f"{SOURCE}: **{info['status']}** ({info['reason']}); overlap is unknown."
    count = sum(row['status'] == 'AVAILABLE' for row in info['providers'].values())
    return (f"{SOURCE}: **AVAILABLE**, {count} provider scopes with IP data, "
            f"{len(info['providers']) - count} without IP data. "
            f"{info['bytes']} bytes, SHA-256 `{info['sha256']}`.")
