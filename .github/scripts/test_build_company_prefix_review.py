import csv
import hashlib
import io
import json
import tarfile
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
            "AS64501\tVK\tVK LLC\thttps://example.test/vk\tyes\tKZ\t0\t1\tno\tyes\n",
            encoding="utf-8",
        )
        prefixes = root / "selected_prefixes.txt"
        prefixes.write_text(
            "# BGP selected prefixes\n"
            "198.51.100.0/24 # AS64500[Yandex],AS64496[RIR-RU]\n"
            "198.51.101.0/24 # AS64500[Yandex]\n"
            "2001:db8:100::/48 # AS64501[VK+RIR-BY/KZ]\n"
            "203.0.113.0/24 # AS64502[RIR-RU]\n",
            encoding="utf-8",
        )
        archive = root / "as-ip-blocks.tar.gz"
        entries = (
            (64500, "TR", ["198.51.100.0/24", "198.51.101.0/24"], []),
            (64501, "RU", [], ["2001:db8:100::/48"]),
            (64496, "RU", ["198.51.100.0/24"], []),
            (64497, "US", ["198.51.100.0/24"], []),
        )
        with tarfile.open(archive, "w:gz") as handle:
            for asn, country, v4, v6 in entries:
                payload = json.dumps({
                    "asn": asn,
                    "metadata": {"countryCode": country},
                    "prefixes": {"ipv4": v4, "ipv6": v6},
                }).encode("utf-8")
                member = tarfile.TarInfo(f"AS{asn}/aggregated.json")
                member.size = len(payload)
                handle.addfile(member, io.BytesIO(payload))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        provenance = root / "input_provenance.tsv"
        provenance.write_text(
            "SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"
            "IPVERSE\tas-ip-blocks.tar.gz\thttps://codeload.github.com/example/archive/master\t"
            + digest + f"\t{archive.stat().st_size}\tdownloaded\n",
            encoding="utf-8",
        )
        return company, manifest, prefixes, provenance, archive

    def test_company_prefixes_include_global_moas_and_exact_address_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance, archive = self.make_inputs(root)
            output = root / "review.tsv"
            stats = root / "stats.txt"
            total, company_only, regional_company = build_review(
                company, manifest, prefixes, provenance, archive, output, stats
            )
            self.assertEqual(total, 3)
            self.assertEqual(company_only, 1)
            self.assertEqual(regional_company, 2)
            with output.open(encoding="utf-8", newline="") as handle:
                rows = [row for row in csv.reader(handle, delimiter="\t") if row]
            header = next(row for row in rows if row[0] == "PREFIX")
            self.assertEqual(header, list(BGP_HEADER))
            data = {row[0]: dict(zip(header, row)) for row in rows if row[0] != "PREFIX" and not row[0].startswith("#")}
            moas = data["198.51.100.0/24"]
            self.assertEqual(moas["STATUS"], "REVIEW")
            self.assertEqual(moas["REGIONAL_RIR_ASN_ORIGIN"], "yes")
            self.assertEqual(moas["INCLUSION_BASIS"], "REGIONAL_RIR_ASN_ORIGIN+COMPANY_ASN")
            self.assertEqual(moas["GLOBAL_BGP_MOAS"], "yes")
            self.assertEqual(moas["GLOBAL_BGP_ORIGIN_ASNS"], "AS64496,AS64497,AS64500")
            self.assertEqual(moas["GLOBAL_BGP_ORIGIN_COUNTRY_CODES"], "AS64496=RU,AS64497=US,AS64500=TR")
            self.assertEqual(moas["RPKI_STATUS"], "NOT_QUERIED")
            self.assertEqual(moas["IRR_STATUS"], "NOT_QUERIED")
            details = json.loads(moas["COMPANY_ASN_DETAILS_JSON"])
            self.assertEqual(details[0]["asn"], "AS64500")
            self.assertEqual(details[0]["ipverse_country_code"], "TR")
            self.assertEqual(details[0]["also_rir_ru"], "no")
            self.assertEqual(details[0]["also_rir_by_kz"], "no")
            self.assertEqual(moas["SELECTED_ORIGIN_ASNS"], "AS64496,AS64500")
            company_only_v4 = data["198.51.101.0/24"]
            self.assertEqual(company_only_v4["INCLUSION_BASIS"], "COMPANY_ASN_ONLY")
            self.assertEqual(company_only_v4["GLOBAL_BGP_MOAS"], "no")
            self.assertEqual(company_only_v4["GLOBAL_BGP_ORIGIN_ASNS"], "AS64500")
            regional_company_v6 = data["2001:db8:100::/48"]
            self.assertEqual(regional_company_v6["FAMILY"], "IPv6")
            self.assertEqual(regional_company_v6["GLOBAL_BGP_ORIGIN_ASNS"], "AS64501")
            self.assertEqual(regional_company_v6["REGIONAL_RIR_ASN_ORIGIN"], "yes")
            self.assertEqual(regional_company_v6["INCLUSION_BASIS"], "REGIONAL_RIR_ASN_ORIGIN+COMPANY_ASN")
            details_v6 = json.loads(regional_company_v6["COMPANY_ASN_DETAILS_JSON"])
            self.assertEqual(details_v6[0]["ipverse_country_code"], "KZ")
            self.assertEqual(details_v6[0]["also_rir_ru"], "no")
            self.assertEqual(details_v6[0]["also_rir_by_kz"], "yes")
            stats_text = stats.read_text(encoding="utf-8")
            self.assertIn("Prefixes with multiple global BGP origin ASNs (MOAS): 1", stats_text)
            self.assertIn("Company-only IPv4 address-space union (independent; may overlap other classes): 256", stats_text)
            self.assertIn("Company-only IPv6 address-space union (independent; may overlap other classes): 0", stats_text)
            self.assertIn("Company+regional-origin IPv6 address-space union (independent): 1208925819614629174706176", stats_text)
            self.assertIn("Company-origin IPv6 address-space union: 1208925819614629174706176", stats_text)

    def test_missing_company_registry_entry_in_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance, archive = self.make_inputs(root)
            manifest.write_text(
                "\t".join(COMPANY_HEADER) + "\n"
                "AS64500\tYandex\tYandex LLC\thttps://example.test/yandex\tyes\tTR\t1\t1\tno\tno\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing registry entries"):
                build_review(company, manifest, prefixes, provenance, archive, root / "review.tsv", root / "stats.txt")

    def test_invalid_bgp_prefix_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance, archive = self.make_inputs(root)
            prefixes.write_text("198.51.100.1/24 # AS64500[Yandex]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid prefix"):
                build_review(company, manifest, prefixes, provenance, archive, root / "review.tsv", root / "stats.txt")

    def test_snapshot_checksum_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance, archive = self.make_inputs(root)
            provenance.write_text(
                "SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"
                "IPVERSE\tas-ip-blocks.tar.gz\thttps://example.test/archive\tnot-a-hash\t1024\tdownloaded\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "valid SHA-256"):
                build_review(company, manifest, prefixes, provenance, archive, root / "review.tsv", root / "stats.txt")

    def test_snapshot_size_must_match_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance, archive = self.make_inputs(root)
            rows = provenance.read_text(encoding="utf-8").splitlines()
            fields = rows[1].split("\\t")
            fields[4] = str(archive.stat().st_size + 1)
            rows[1] = "\\t".join(fields)
            provenance.write_text("\\n".join(rows) + "\\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "BGP snapshot size mismatch"):
                build_review(company, manifest, prefixes, provenance, archive, root / "review.tsv", root / "stats.txt")

    def test_global_bgp_archive_must_cover_every_company_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, prefixes, provenance, archive = self.make_inputs(root)
            with tarfile.open(archive, "w:gz") as handle:
                payload = json.dumps({
                    "asn": 64500, "metadata": {"countryCode": "TR"},
                    "prefixes": {"ipv4": ["198.51.100.0/24"], "ipv6": []},
                }).encode("utf-8")
                member = tarfile.TarInfo("AS64500/aggregated.json")
                member.size = len(payload)
                handle.addfile(member, io.BytesIO(payload))
            provenance.write_text(
                "SOURCE\tLOCAL_FILE\tFETCH_URL\tSHA256\tBYTES\tSTATUS\n"
                "IPVERSE\tas-ip-blocks.tar.gz\thttps://example.test/archive\t"
                + hashlib.sha256(archive.read_bytes()).hexdigest()
                + f"\t{archive.stat().st_size}\tdownloaded\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "absent from the global BGP snapshot"):
                build_review(company, manifest, prefixes, provenance, archive, root / "review.tsv", root / "stats.txt")


if __name__ == "__main__":
    unittest.main()
