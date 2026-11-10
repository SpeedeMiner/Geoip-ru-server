import tempfile
import unittest
from pathlib import Path

from build_company_prefix_review import build_review, BGP_HEADER, COMPANY_HEADER


class CompanyPrefixReviewTests(unittest.TestCase):
    def make_inputs(self, root: Path):
        company = root / "company_asns.tsv"
        company.write_text(
            "# default\n"
            "AS64500\tYandex\tYandex LLC\thttps://example.test/yandex\n"
            "AS64501\tVK\tVK LLC\thttps://example.test/vk\n",
            encoding="utf-8",
        )
        manifest = root / "company_manifest.tsv"
        manifest.write_text(
            "\t".join(COMPANY_HEADER) + "\n"
            "AS64500\tYandex\tYandex LLC\thttps://example.test/yandex\tyes\tTR\t1\t1\tno\tno\n"
            "AS64501\tVK\tVK LLC\thttps://example.test/vk\tyes\tRU\t1\t0\tno\tno\n",
            encoding="utf-8",
        )
        prefixes = root / "selected_prefixes.txt"
        prefixes.write_text(
            "# BGP selected prefixes\n"
            "198.51.100.0/24 # AS64500[Yandex],AS64496[RIR-RU]\n"
            "198.51.101.0/24 # AS64500[Yandex]\n"
            "2001:db8:100::/48 # AS64501[VK]\n"
            "203.0.113.0/24 # AS64502[RIR-RU]\n",
            encoding="utf-8",
        )
        provenance = root / "input_provenance.tsv"
        provenance.write_text(
            "SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"
            "IPVERSE\tas-ip-blocks.tar.gz\thttps://codeload.github.com/example/archive/master\t"
            + "a" * 64 + "\t1024\tdownloaded\n",
            encoding="utf-8",
        )
        return company, manifest, prefixes, provenance

    def test_company_prefixes_are_review_only_and_exactly_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance = self.make_inputs(root)
            output = root / "review.tsv"
            stats = root / "stats.txt"
            total, company_only, _ = build_review(company, manifest, prefixes, provenance, output, stats)

            self.assertEqual(total, 3)
            self.assertEqual(company_only, 2)
            rows = output.read_text(encoding="utf-8").splitlines()
            header = next(row for row in rows if row.startswith("PREFIX\t"))
            self.assertEqual(header.split("\t"), list(BGP_HEADER))
            data = [row.split("\t") for row in rows if row and not row.startswith("#") and not row.startswith("PREFIX\t")]
            self.assertEqual(len(data), 3)
            by_prefix = {row[0]: row for row in data}

            self.assertEqual(by_prefix["198.51.100.0/24"][13], "REVIEW")
            self.assertEqual(by_prefix["198.51.100.0/24"][9], "yes")
            self.assertEqual(by_prefix["198.51.100.0/24"][10], "REGIONAL_RIR_ASN_ORIGIN+COMPANY_ASN")
            self.assertEqual(by_prefix["198.51.101.0/24"][10], "COMPANY_ASN_ONLY")
            self.assertEqual(by_prefix["2001:db8:100::/48"][1], "IPv6")
            self.assertEqual(by_prefix["2001:db8:100::/48"][11], "NOT_QUERIED")
            self.assertEqual(by_prefix["2001:db8:100::/48"][12], "NOT_QUERIED")
            self.assertEqual(by_prefix["198.51.101.0/24"][14], "PRESENT_IN_SELECTED_BGP_INPUT")
            self.assertIn("Company-only IPv4 address-space union (independent; may overlap other classes): 256",
                          stats.read_text(encoding="utf-8"))
            self.assertIn("Company-origin IPv6 address-space union: 1208925819614629174706176",
                          stats.read_text(encoding="utf-8"))

    def test_missing_company_registry_entry_in_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance = self.make_inputs(root)
            manifest.write_text(
                "\t".join(COMPANY_HEADER) + "\n"
                "AS64500\tYandex\tYandex LLC\thttps://example.test/yandex\tyes\tTR\t1\t1\tno\tno\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing registry entries"):
                build_review(company, manifest, prefixes, provenance, root / "review.tsv", root / "stats.txt")

    def test_invalid_bgp_prefix_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance = self.make_inputs(root)
            prefixes.write_text("198.51.100.1/24 # AS64500[Yandex]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid prefix"):
                build_review(company, manifest, prefixes, provenance, root / "review.tsv", root / "stats.txt")

    def test_snapshot_checksum_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance = self.make_inputs(root)
            provenance.write_text(
                "SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"
                "IPVERSE\tas-ip-blocks.tar.gz\thttps://example.test/archive\tnot-a-hash\t1024\tdownloaded\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "valid SHA-256"):
                build_review(company, manifest, prefixes, provenance, root / "review.tsv", root / "stats.txt")


if __name__ == "__main__":
    unittest.main()
