"""Evidence registry for reviewed IP-layer unreachability, not domain/SNI blocks."""
import csv
from datetime import date, datetime, timezone
import ipaddress
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "v41-reviewed-unreachable.tsv"
HEADER = ["cidr", "kind", "evidence", "verified_on", "review_after"]
KINDS = {"IP_LAYER_BLOCK", "INBOUND_GEO_IP_BLOCK"}


def read_reviewed(path=DEFAULT_PATH, *, as_of=None):
    """Return canonical rows; an empty, correctly headed registry has no routing effect."""
    today = as_of or datetime.now(timezone.utc).date()
    rows = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != HEADER:
            raise ValueError(f"{path}: invalid reviewed-unreachable header")
        for row in reader:
            if None in row or any(not row.get(k) for k in HEADER):
                raise ValueError(f"{path}:{reader.line_num}: missing or extra field")
            prefix = row["cidr"]
            net = ipaddress.ip_network(prefix, strict=True)
            if prefix != str(net) or net.prefixlen == 0 or prefix in rows:
                raise ValueError(f"{path}:{reader.line_num}: invalid, default or duplicate prefix")
            url = urlsplit(row["evidence"])
            if (row["kind"] not in KINDS or url.scheme != "https" or not url.hostname or not url.path
                    or url.username or url.password or url.fragment
                    or any(c.isspace() for c in row["evidence"])):
                raise ValueError(f"{path}:{reader.line_num}: invalid IP evidence type or URL")
            verified = date.fromisoformat(row["verified_on"])
            review = date.fromisoformat(row["review_after"])
            if (verified.isoformat() != row["verified_on"] or review.isoformat() != row["review_after"]
                    or verified > today or review < verified or today > review):
                raise ValueError(f"{path}:{reader.line_num}: evidence is future-dated or due for review")
            rows[prefix] = row
    return rows
