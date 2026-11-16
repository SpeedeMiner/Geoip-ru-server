from datetime import date
import ipaddress
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_v41_overlay import encode_geoip
import validate_v41_routing_matrix as matrix


class RoutingMatrixTests(unittest.TestCase):
    def test_official_fixtures_are_partial_and_dual_stack(self):
        path = Path(__file__).resolve().parent.parent / "data/v41-routing-fixtures.tsv"
        rows = matrix.read_fixtures(path, as_of=date(2026, 11, 16))
        self.assertEqual({ipaddress.ip_address(r["address"]).version for r in rows}, {4, 6})
        self.assertTrue(all(r["expected"] == "DIRECT" for r in rows))

    def test_matrix_checks_dat_and_both_srs_categories(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            dat, ru, private = (root / name for name in ("test.dat", "ru.json", "private.json"))
            categories = {"RU": {ipaddress.ip_network("192.0.2.0/24"), ipaddress.ip_network("2001:db8::/48")},
                          "PRIVATE": {ipaddress.ip_network("10.0.0.0/8")}}
            dat.write_bytes(encode_geoip(categories))
            for path, key in ((ru, "RU"), (private, "PRIVATE")):
                path.write_text(json.dumps({"version": 1, "rules": [{"ip_cidr": [str(n) for n in categories[key]]}]}), encoding="utf-8")
            sources = {"RU": matrix.read_srs_source(ru), "PRIVATE": matrix.read_srs_source(private)}
            rows = [{"service": "local", "address": "192.0.2.1", "expected": "DIRECT"},
                    {"service": "outside", "address": "198.51.100.1", "expected": "PROXY"}]
            self.assertEqual(matrix.validate_matrix(dat, sources, rows)["fixtures"], 2)
            with self.assertRaisesRegex(ValueError, "routing fixture failed"):
                matrix.validate_matrix(dat, sources, [{**rows[0], "expected": "PROXY"}])
            with self.assertRaisesRegex(ValueError, "SRS coverage differs"):
                matrix.validate_matrix(dat, {**sources, "RU": set()}, rows)

    def test_sni_evidence_and_expired_records_cannot_assert_proxy(self):
        header = "\t".join(matrix.HEADER) + "\n"
        row = "test\t192.0.2.1\tPROXY\tVERIFIED_IP_UNREACHABLE\thttps://example.test/evidence\t2026-11-15\t2026-12-01\n"
        with TemporaryDirectory() as folder:
            path = Path(folder) / "fixtures"
            for invalid in (row.replace("VERIFIED_IP_UNREACHABLE", "SNI_BLOCK"), row.replace("2026-12-01", "2026-11-15")):
                path.write_text(header + invalid, encoding="utf-8")
                with self.assertRaises(ValueError):
                    matrix.read_fixtures(path, as_of=date(2026, 11, 16))
