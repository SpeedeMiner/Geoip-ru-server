import datetime as dt
import tempfile
import unittest
from pathlib import Path

from build_rir_rukzby_prefixes import build, parse_resource, snapshot_header


class RegionalRirInventoryTests(unittest.TestCase):
    def test_ipv4_resource_expands_to_minimal_cidrs(self):
        self.assertEqual(parse_resource("RU", "ipv4", "192.0.2.0", "256"), ["192.0.2.0/24"])

    def test_ipv6_resource_uses_prefix_length(self):
        self.assertEqual(parse_resource("KZ", "ipv6", "2001:db8:1::", "48"), ["2001:db8:1::/48"])

    def test_rejects_wrong_family_and_default_route(self):
        self.assertEqual(parse_resource("RU", "ipv4", "2001:db8::", "2"), [])
        self.assertEqual(parse_resource("RU", "ipv6", "::", "0"), [])

    def test_snapshot_header_requires_matching_registry(self):
        with self.assertRaises(ValueError):
            snapshot_header(["2|apnic|3|20260101|20260101|20260101|1"], "arin")

    def test_build_keeps_country_registry_and_status_provenance(self):
        today = dt.date.today().strftime("%Y%m%d")
        content = "\n".join([
            f"2|afrinic|3|20200101|20200101|{today}|1",
            f"afrinic|RU|ipv4|192.0.2.0|256|20200101|allocated",
            f"afrinic|BY|ipv6|2001:db8:1::|48|20200101|assigned",
            f"afrinic|KZ|ipv4|198.51.100.0|256|20200101|legacy",
            f"afrinic|RU|ipv4|203.0.113.0|256|20200101|available",
            "",
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "afrinic"
            path.write_text(content, encoding="utf-8")
            rows, _ = build({name: path if name == "afrinic" else _stub_snapshot(name, tmp, today) for name in ("afrinic", "apnic", "arin", "lacnic", "ripencc")})
        self.assertEqual({(r["country"], r["prefix"], r["registry"], r["status"]) for r in rows}, {
            ("RU", "192.0.2.0/24", "afrinic", "allocated"),
            ("BY", "2001:db8:1::/48", "afrinic", "assigned"),
            ("KZ", "198.51.100.0/24", "afrinic", "legacy"),
        })


def _stub_snapshot(registry, tmp, today):
    p = Path(tmp) / registry
    p.write_text(f"2|{registry}|3|20200101|20200101|{today}|1\n", encoding="utf-8")
    return p


if __name__ == "__main__":
    unittest.main()
