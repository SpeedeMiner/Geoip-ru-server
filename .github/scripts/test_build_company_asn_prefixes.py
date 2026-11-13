import tempfile
import unittest
from pathlib import Path

from build_company_asn_prefixes import build_company_prefixes, read_company_asns, read_rir_ru_asns


class CompanyASNPrefixTests(unittest.TestCase):
    def _write_registry(self, path: Path) -> None:
        rows = [
            f"AS{asn}\tGroup {asn}\tCompany {asn}\thttps://example.test/AS{asn}"
            for asn in range(100, 112)
        ]
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def _write_rir_ru(self, path: Path) -> None:
        rows = [f"AS{asn}" for asn in range(64500, 64512)]
        path.write_text("# RIR-RU ASNs\n" + "\n".join(rows) + "\n", encoding="utf-8")

    def test_extracts_only_prefixes_with_allowlisted_exact_origins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "company.tsv"
            selected = root / "selected.txt"
            output = root / "company-prefixes.txt"
            self._write_registry(registry)
            selected.write_text(
                "# selected origin prefixes\n"
                "198.51.100.0/24 # AS100[Group_100],AS64500[RIR-RU]\n"
                "203.0.113.0/24 # AS64501[RIR-RU]\n"
                "2001:db8:100::/48 # AS111[Group_111]\n",
                encoding="utf-8",
            )
            result = build_company_prefixes(selected, registry, output)
            body = output.read_text(encoding="utf-8")
            self.assertEqual(result["unique_prefixes"], 2)
            self.assertIn("198.51.100.0/24 # AS100", body)
            self.assertIn("2001:db8:100::/48 # AS111", body)
            self.assertNotIn("203.0.113.0/24", body)

    def test_extracts_both_corporate_and_rir_ru_asn_prefixes_when_rir_ru_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "company.tsv"
            rir_ru = root / "rir-ru.txt"
            selected = root / "selected.txt"
            output = root / "company-prefixes.txt"
            self._write_registry(registry)
            self._write_rir_ru(rir_ru)
            selected.write_text(
                "# selected origin prefixes\n"
                "198.51.100.0/24 # AS100[Group_100],AS64500[RIR-RU]\n"
                "203.0.113.0/24 # AS64501[RIR-RU]\n"
                "192.0.2.0/24 # AS65001[RIR-BY/KZ]\n"
                "2001:db8:100::/48 # AS111[Group_111]\n",
                encoding="utf-8",
            )
            result = build_company_prefixes(selected, registry, output, rir_ru_registry=rir_ru)
            body = output.read_text(encoding="utf-8")
            self.assertEqual(result["unique_prefixes"], 3)
            self.assertEqual(result["active_company_asns"], 2)
            self.assertEqual(result["active_rir_ru_asns"], 2)
            self.assertIn("198.51.100.0/24 # AS100,AS64500", body)
            self.assertIn("203.0.113.0/24 # AS64501", body)
            self.assertIn("2001:db8:100::/48 # AS111", body)
            self.assertNotIn("192.0.2.0/24", body)
            self.assertIn("rir_ru_asn_registry_sha256", result)

    def test_moas_prefix_is_exempt_when_any_exact_origin_is_corporate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "company.tsv"
            selected = root / "selected.txt"
            output = root / "company-prefixes.txt"
            self._write_registry(registry)
            selected.write_text("192.0.2.0/24 # AS64500,AS105\n", encoding="utf-8")
            result = build_company_prefixes(selected, registry, output)
            self.assertEqual(result["active_company_asns"], 1)
            self.assertIn("192.0.2.0/24 # AS105", output.read_text(encoding="utf-8"))

    def test_regional_origin_uses_both_registries_and_not_provenance_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, ru, by_kz, selected, output = (root / x for x in ("company", "ru", "by-kz", "input", "out"))
            self._write_registry(company)
            self._write_rir_ru(ru)
            by_kz.write_text("".join(f"AS{asn}\n" for asn in range(65000, 65012)), encoding="utf-8")
            selected.write_text(
                "192.0.2.0/24 # AS65000[RIR-BY/KZ]\n"
                "198.51.100.0/24 # AS64500[RIR-RU],AS65001[RIR-BY/KZ]\n"
                "203.0.113.0/24 # AS60000[RIR-BY/KZ]\n"
                "2001:db8::/48 # AS65002[RIR-BY/KZ]\n",
                encoding="utf-8",
            )
            result = build_company_prefixes(selected, company, output, ru, by_kz)
            body = output.read_text(encoding="utf-8")
            self.assertEqual(result["active_rir_by_kz_asns"], 3)
            self.assertIn("rir_by_kz_asn_registry_sha256=", body)
            self.assertIn("192.0.2.0/24 # AS65000", body)
            self.assertIn("198.51.100.0/24 # AS64500,AS65001", body)
            self.assertIn("2001:db8::/48 # AS65002", body)
            self.assertNotIn("203.0.113.0/24", body)

    def test_static_direct_company_origin_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "company.tsv"
            selected = root / "selected.txt"
            output = root / "company-prefixes.txt"
            self._write_registry(registry)
            selected.write_text("45.148.65.0/24 # AS212066[Yandex][STATIC-DIRECT]\n", encoding="utf-8")
            registry.write_text(registry.read_text(encoding="utf-8") + "AS212066\tYandex\tYandex Turkey\thttps://example.test/yandex\n", encoding="utf-8")
            result = build_company_prefixes(selected, registry, output)
            self.assertEqual(result["unique_prefixes"], 1)

    def test_malformed_or_unprovenanced_selected_row_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "company.tsv"
            selected = root / "selected.txt"
            output = root / "out.txt"
            self._write_registry(registry)
            selected.write_text("not-a-prefix # AS100\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_company_prefixes(selected, registry, output)
            selected.write_text("192.0.2.0/24\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_company_prefixes(selected, registry, output)

    def test_empty_corporate_origin_match_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "company.tsv"
            selected = root / "selected.txt"
            output = root / "out.txt"
            self._write_registry(registry)
            selected.write_text("192.0.2.0/24 # AS64500\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_company_prefixes(selected, registry, output)


if __name__ == "__main__":
    unittest.main()
