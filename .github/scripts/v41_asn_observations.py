"""Prefix classification shared by v41 extraction and advisory ASN audit."""
import ipaddress


def classify_prefix(raw, version):
    token = str(raw)
    try:
        network = ipaddress.ip_network(token, strict=False)
    except ValueError:
        return "invalid", None
    if network.version != version:
        return "wrong_family", None
    if network.prefixlen == 0:
        return "default", None
    if ipaddress.ip_address(token.split("/", 1)[0]) != network.network_address:
        return "normalized", network
    return "valid", network


def parse_announced_prefixes(prefixes):
    parsed = []
    invalid = normalized = 0
    for family, version in (("ipv4", 4), ("ipv6", 6)):
        for raw in prefixes.get(family, []) or []:
            outcome, network = classify_prefix(raw, version)
            if network is None:
                invalid += 1
                continue
            normalized += outcome == "normalized"
            parsed.append((family, network))
    return parsed, invalid, normalized
