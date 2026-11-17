from datetime import date
import ipaddress
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_v41_overlay import encode_geoip
import validate_v41_routing_matrix as matrix


class RoutingMatrixTests(unittest.TestCase):
    def test_official_fixtures_cover_both_families_and_expected_policy(self):
        path = Path(__file__).resolve().parent.parent / "data/v41-routing-fixtures.tsv"
        rows = matrix.read_fixtures(path, as_of=date(2026, 11, 16))
        self.assertEqual({ipaddress.ip_address(r["address"]).version for r in rows}, {4, 6})
        for kind, expected, count in (("OFFICIAL_SERVICE_IP", "DIRECT", 2),
                                      ("IANA_TLD_GLUE", "DIRECT", 4),
                                      ("TELEGRAM_POLICY_EXCLUSION", "PROXY", 2)):
            group = [r for r in rows if r["evidence_type"] == kind]
            self.assertEqual(len(group), count)
            self.assertEqual({ipaddress.ip_address(r["address"]).version for r in group}, {4, 6})
            self.assertTrue(all(r["expected"] == expected for r in group))
        for url in matrix.IANA_TLDS:
            self.assertEqual({ipaddress.ip_address(r["address"]).version for r in rows
                              if r["evidence_url"] == url}, {4, 6})

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

    def test_telegram_policy_is_bound_to_feed_and_not_live_unreachability(self):
        header = "\t".join(matrix.HEADER) + "\n"
        row = ("Telegram test\t91.108.4.1\tPROXY\tTELEGRAM_POLICY_EXCLUSION\t"
               f"{matrix.TELEGRAM_CIDR_URL}\t2026-11-16\t2026-12-01\n")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "fixtures"
            feed = Path(folder) / "telegram"
            as_of = date(2026, 11, 16)
            path.write_text(header + row, encoding="utf-8")
            self.assertEqual(matrix.read_fixtures(path, as_of=as_of)[0]["evidence_type"],
                             "TELEGRAM_POLICY_EXCLUSION")
            feed.write_text("149.154.160.0/20\n2001:67c:4e8::/48\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "lacks official Telegram policy evidence"):
                matrix.read_fixtures(path, as_of=as_of, telegram_feed=feed)
            for bad in (row.replace("91.108.4.1", "8.8.8.8"), row.replace("PROXY", "DIRECT"),
                        row.replace(matrix.TELEGRAM_CIDR_URL, "https://example.test/cidr.txt")):
                with self.subTest(row=bad):
                    path.write_text(header + bad, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        matrix.read_fixtures(path, as_of=as_of)

    def test_iana_fixture_rejects_nonofficial_source_and_proxy(self):
        header = "\t".join(matrix.HEADER) + "\n"
        row = ("test\t93.125.25.72\tDIRECT\tIANA_TLD_GLUE\thttps://www.iana.org/domains/root/db/by.html"
               "\t2026-11-16\t2026-12-01\n")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "fixtures"
            for bad in (row.replace("www.iana.org", "example.test"), row.replace("DIRECT", "PROXY")):
                path.write_text(header + bad, encoding="utf-8")
                with self.assertRaises(ValueError):
                    matrix.read_fixtures(path, as_of=date(2026, 11, 16))
