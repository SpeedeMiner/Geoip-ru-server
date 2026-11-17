"""Explicit DIRECT admission for reviewed foreign conflicts and measured CDN IPs."""
import csv
from datetime import date, datetime, timezone
import hashlib
import ipaddress
from pathlib import Path
import re
from urllib.parse import urlsplit

CDN_PATH = Path(__file__).resolve().parents[1] / "data/v41-reviewed-reachable-cdn.tsv"
CDN_KEY = "reviewed_reachable_cdn"
ROLE = "exact-foreign-admission-review"
HEADER = ["address", "provider", "provider_evidence", "ru_asn", "ru_measurement", "verified_on", "review_after"]


def evidence_url(value):
    url = urlsplit(value)
    return (url.scheme == "https" and url.hostname and url.path not in {"", "/"}
            and not (url.username or url.password or url.fragment or any(c.isspace() for c in value)))


def read_cdn(path=CDN_PATH, *, as_of=None):
    """An explicitly reviewed measurement grants one exact public IP, never a CIDR."""
    today = as_of or datetime.now(timezone.utc).date()
    rows = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != HEADER:
            raise ValueError(f"{path}: invalid CDN review header")
        for row in reader:
            try:
                if None in row or any(not row[k] or row[k] != row[k].strip() for k in HEADER):
                    raise ValueError("missing or malformed CDN evidence")
                addr = ipaddress.ip_address(row["address"])
                if (str(addr) != row["address"] or addr in rows or not addr.is_global
                        or addr.is_multicast or addr.is_reserved
                        or getattr(addr, "ipv4_mapped", None) is not None):
                    raise ValueError("expected one canonical, public CDN IP")
                asn = row["ru_asn"]
                if not re.fullmatch(r"AS[1-9][0-9]{0,9}", asn) or int(asn[2:]) > 4294967295:
                    raise ValueError("invalid measurement source ASN")
                if (not evidence_url(row["provider_evidence"]) or not evidence_url(row["ru_measurement"])
                        or row["provider_evidence"] == row["ru_measurement"]):
                    raise ValueError("separate provider and Russian measurement evidence are required")
                verified, review = (date.fromisoformat(row[k]) for k in ("verified_on", "review_after"))
                if (verified.isoformat() != row["verified_on"] or review.isoformat() != row["review_after"]
                        or not verified <= today <= review):
                    raise ValueError("CDN evidence is future-dated or due for review")
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{reader.line_num}: {exc}") from exc
            rows[addr] = row
    return rows


def cdn_networks(rows):
    return {ipaddress.ip_network((addr, addr.max_prefixlen)) for addr in rows}


def verify_cdn_manifest(manifest, path=CDN_PATH):
    rows = read_cdn(path)
    if (manifest.get("input_sha256", {}).get(CDN_KEY) != hashlib.sha256(path.read_bytes()).hexdigest()
            or manifest.get(CDN_KEY, {}).get("records") != list(rows.values())):
        raise ValueError("Reviewed CDN evidence provenance mismatch")
    return rows
