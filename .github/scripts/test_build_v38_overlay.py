import ipaddress
import json
import tempfile
import unittest
from pathlib import Path

import build_v38_overlay as build


class GeoIPV38OverlayTests(unittest.TestCase):
    def test_protobuf_roundtrip_preserves_only_ru_and_private_categories(self):
        entries = {
            "RU": {ipaddress.ip_network("1.2.3.0/24"), ipaddress.ip_network("2001:db8::/32")},
            "PRIVATE": {ipaddress.ip_network("10.0.0.0/8")},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"out.dat"
            path.write_bytes(build.encode_geoip(entries))
            self.assertEqual(build.parse_geoip_dat(path), {"RU":set(build.collapse(entries["RU"])),"PRIVATE":set(build.collapse(entries["PRIVATE"]))})

    def test_interval_subtraction_and_intersection(self):
        a=build.intervals([ipaddress.ip_network("198.51.100.0/24")],4)
        b=build.intervals([ipaddress.ip_network("198.51.100.0/25")],4)
        self.assertEqual(build.interval_size(build.subtract(a,b)),128)
        self.assertEqual(build.interval_size(build.intersect(a,b)),128)

    def test_cidr_set_subtraction_carves_more_specific_private_and_rkn_ranges(self):
        direct = {
            ipaddress.ip_network("203.0.113.0/24"),
            ipaddress.ip_network("2001:db8:100::/48"),
        }
        private = {
            ipaddress.ip_network("203.0.113.0/26"),
            ipaddress.ip_network("2001:db8:100:1::/64"),
        }
        blocked = {
            ipaddress.ip_network("203.0.113.128/25"),
            ipaddress.ip_network("2001:db8:100:2::/64"),
        }
        final = build.subtract_networks(direct, private, blocked)
        self.assertEqual(build.addr_counts(final), {
            "ipv4": 64,
            "ipv6": (1 << 80) - (1 << 64) - (1 << 64),
        })
        for mask in private | blocked:
            mask_intervals = build.intervals([mask], mask.version)
            self.assertEqual(build.intersect(build.intervals(final, mask.version), mask_intervals), [])


    def test_ipsum_requires_exact_ipv4_24_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"ipsum"
            p.write_text("".join(f"198.51.{i}.0/24\n" for i in range(1001)),encoding="utf-8")
            nets, stats=build.parse_ipsum(p)
            self.assertEqual(len(nets),1001)
            self.assertEqual(stats["invalid_rows"],0)
            p.write_text("198.51.100.0/23\n",encoding="utf-8")
            with self.assertRaises(ValueError):
                build.parse_ipsum(p)

    def test_services_json_extracts_tiered_service_provenance(self):
        data={"generatedAt":"2026-11-11T00:00:00Z","categories":[{"id":"banks","services":[
            {"name":"Bank A","tier":"lite","domains":3,"asns":[123],"ipv4":["1.2.3.0/24"],"ipv6":["2001:db8::/32"]},
            {"name":"Bank B","tier":"standard","domains":2,"asns":[],"ipv4":["2.3.4.0/24"],"ipv6":[]},
            {"name":"ignored","tier":"full","domains":1,"ipv4":["3.4.5.0/24"],"ipv6":[]},
        ]}]}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"services.json"
            p.write_text(json.dumps(data),encoding="utf-8")
            nets,rows,count,generated=build.parse_services_json(p)
        self.assertEqual(count,2)
        self.assertEqual(len(nets),3)
        self.assertEqual(generated,data["generatedAt"])
        self.assertTrue(any(r["service"]=="Bank A" and r["prefix"]=="2001:db8::/32" for r in rows))

    def test_private_and_blocked_precedence_math(self):
        base={ipaddress.ip_network("198.51.100.0/24")}
        additions={ipaddress.ip_network("198.51.101.0/24")}
        private={ipaddress.ip_network("198.51.101.0/25")}
        blocked={ipaddress.ip_network("198.51.101.128/32")}
        final=build.intervals(base|additions,4)
        final=build.subtract(final,build.intervals(private,4))
        final=build.subtract(final,build.intervals(blocked,4))
        self.assertEqual(build.interval_size(final),127+256)


if __name__ == "__main__":
    unittest.main()
