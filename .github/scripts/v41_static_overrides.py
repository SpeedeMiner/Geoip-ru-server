"""Parse reviewed static DIRECT overrides; never claim they are BGP observations."""
import csv
from datetime import date
import ipaddress
from pathlib import Path
import re

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "v41-static-overrides.tsv"
HEADER = ["cidr", "asn", "reason", "added_date", "review_after"]


def read_overrides(path=DEFAULT_PATH):
    overrides = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != HEADER:
            raise ValueError(f"{path}: unexpected override schema")
        for row in reader:
            if None in row or any(not row.get(k) for k in HEADER):
                raise ValueError(f"{path}:{reader.line_num}: missing or extra field")
            net = ipaddress.ip_network(row["cidr"], strict=True)
            if str(net) != row["cidr"] or net.prefixlen == 0:
                raise ValueError(f"{path}:{reader.line_num}: noncanonical or default route")
            match = re.fullmatch(r"AS([1-9][0-9]*)", row["asn"])
            if not match or int(match[1]) > 4294967295:
                raise ValueError(f"{path}:{reader.line_num}: invalid ASN")
            added, review = date.fromisoformat(row["added_date"]), date.fromisoformat(row["review_after"])
            if review < added or row["reason"] != row["reason"].strip():
                raise ValueError(f"{path}:{reader.line_num}: invalid review metadata")
            key = str(net)
            if key in overrides:
                raise ValueError(f"{path}:{reader.line_num}: duplicate prefix")
            overrides[key] = {**row, "asn_number": int(match[1])}
    if not overrides:
        raise ValueError(f"{path}: empty override registry")
    return overrides


def unobserved(overrides, observed_origins):
    """An aggregated observation covers a pin only with the same origin ASN."""
    by_family_asn = {}
    wanted = {(ipaddress.ip_network(prefix).version, row["asn_number"]) for prefix, row in overrides.items()}
    for prefix, origins in observed_origins.items():
        net = ipaddress.ip_network(prefix, strict=True)
        for asn in origins:
            key = (net.version, asn)
            if key in wanted:
                by_family_asn.setdefault(key, []).append(net)
    by_family_asn = {key: list(ipaddress.collapse_addresses(nets)) for key, nets in by_family_asn.items()}
    for prefix, row in overrides.items():
        net = ipaddress.ip_network(prefix)
        if not any(net.subnet_of(route) for route in by_family_asn.get((net.version, row["asn_number"]), ())):
            yield prefix, row


def expected_quality_markers(overrides):
    ordered = sorted(overrides, key=lambda value: (
        ipaddress.ip_network(value).version,
        int(ipaddress.ip_network(value).network_address),
        ipaddress.ip_network(value).prefixlen,
    ))
    listing = ", ".join(ordered)
    count = len(ordered)
    return (
        f"Static DIRECT override list: {listing}",
        f"Static DIRECT selected overrides: {count} of {count}",
        f"Static DIRECT final prefix checks (after PRIVATE/blocked carve): {count} of {count}",
        f"Static DIRECT final prefix list: {listing}",
    )
