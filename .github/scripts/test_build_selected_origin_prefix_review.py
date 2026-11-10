import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from build_company_prefix_review import COMPANY_HEADER
from build_selected_origin_prefix_review import build_review, HEADER


class SelectedOriginPrefixReviewTests(unittest.TestCase):
    def make_inputs(self, root: Path):
        company = root / "company_asns.tsv"
        company.write_text(
            "AS64500\tYandex\tYandex LLC\thttps://example.test/yandex\n",
            encoding="utf-8",
        )
        manifest = root / "company_manifest.tsv"
        manifest.write_text(
            "\t".join(COMPANY_HEADER) + "\n"
            "AS64500\tYandex\tYandex LLC\thttps://example.test/yandex\tyes\tTR\t1\t0\tno\tno\n",
            encoding="utf-8",
        )
        selected = root / "selected_prefixes.txt"
        selected.write_text(
            "# selected BGP prefixes\n"
            "198.51.100.0/24 # AS64500[Yandex],AS64496[RIR-RU]\n"
            "198.51.101.0/24 # AS64500[Yandex]\n"
            "2001:db8:100::/48 # AS64501[RIR-BY/KZ]\n"
            "203.0.113.0/24 # AS64497[RIR-RU]\n",
            encoding="utf-8",
        )
        archive = root / "as-ip-blocks.tar.gz"
        entries = (
            (64500, "TR", ["198.51.100.0/24", "198.51.101.0/24"], []),
            (64501, "KZ", [], ["2001:db8:100::/48"]),
            (64496, "RU", ["198.51.100.0/24"], []),
            (64497, "RU", ["203.0.113.0/24"], []),
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
            "IPVERSE\tas-ip-blocks.tar.gz\thttps://example.test/archive\t"
            + digest + f"\t{archive.stat().st_size}\tdownloaded\n",
            encoding="utf-8",
        )
        return company, manifest, selected, provenance, archive

    def test_all_selected_prefixes_are_emitted_and_remain_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, selected, provenance, archive = self.make_inputs(root)
            output = root / "selected-review.tsv"
            stats = root / "selected-review-stats.txt"
            total, company_count, moas_count = build_review(
                selected, company, manifest, provenance, archive, output, stats
            )
            self.assertEqual(total, 4)
            self.assertEqual(company_count, 2)
            self.assertEqual(moas_count, 1)

            rows = [line.split("\t") for line in output.read_text(encoding="utf-8").splitlines()
                    if line and not line.startswith("#")]
            self.assertEqual(rows[0], list(HEADER))
            data = {row[0]: dict(zip(HEADER, row)) for row in rows[1:]}
            dual = data["198.51.100.0/24"]
            self.assertEqual(dual["COMPANY_ASNS"], "AS64500")
            self.assertEqual(dual["REGIONAL_RIR_ORIGIN_ASNS"], "AS64496")
            self.assertEqual(dual["INCLUSION_BASIS"], "REGIONAL_RIR_ASN+COMPANY_ASN")
            self.assertEqual(dual["GLOBAL_BGP_ORIGIN_ASNS"], "AS64496,AS64500")
            self.assertEqual(dual["GLOBAL_BGP_MOAS"], "yes")
            self.assertEqual(dual["STATUS"], "REVIEW")
            self.assertEqual(dual["RPKI_STATUS"], "NOT_QUERIED")
            self.assertEqual(dual["IRR_STATUS"], "NOT_QUERIED")

            company_only = data["198.51.101.0/24"]
            self.assertEqual(company_only["INCLUSION_BASIS"], "COMPANY_ASN_ONLY")
            regional_only = data["2001:db8:100::/48"]
            self.assertEqual(regional_only["FAMILY"], "IPv6")
            self.assertEqual(regional_only["INCLUSION_BASIS"], "REGIONAL_RIR_ASN_ONLY")
            self.assertEqual(data["203.0.113.0/24"]["COMPANY_ASNS"], "")
            stats_text = stats.read_text(encoding="utf-8")
            self.assertIn("Unique selected regional/company origin prefixes: 4", stats_text)
            self.assertIn("Prefixes with at least one company origin ASN: 2", stats_text)
            self.assertIn("Prefixes with at least one regional RIR-RU/BY/KZ origin ASN: 3", stats_text)
            self.assertIn("Prefixes with multiple exact global BGP origin ASNs (MOAS): 1", stats_text)
            self.assertIn("Review status: REVIEW for every row", stats_text)

    def test_selected_prefix_missing_from_global_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, selected, provenance, archive = self.make_inputs(root)
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
                build_review(selected, company, manifest, provenance, archive,
                             root / "review.tsv", root / "stats.txt")

    def test_unknown_selected_origin_role_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, selected, provenance, archive = self.make_inputs(root)
            selected.write_text("192.0.2.0/24 # AS64502[UNKNOWN]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no company or regional RIR origin label"):
                build_review(selected, company, manifest, provenance, archive,
                             root / "review.tsv", root / "stats.txt")



    def test_static_direct_pin_missing_from_snapshot_is_retained_as_not_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            company, manifest, selected, provenance, archive = self.make_inputs(root)
            with selected.open("a", encoding="utf-8") as handle:
                handle.write("192.0.2.0/24 # AS64500[Yandex+STATIC-DIRECT]\n")
            output = root / "selected-review.tsv"
            stats = root / "selected-review-stats.txt"
            build_review(selected, company, manifest, provenance, archive, output, stats)
            rows = [row for row in output.read_text(encoding="utf-8").splitlines()
                    if row.startswith("192.0.2.0/24\t")]
            self.assertEqual(len(rows), 1)
            data = dict(zip(HEADER, rows[0].split("\t")))
            self.assertEqual(data["GLOBAL_BGP_ORIGIN_ASNS"], "")
            self.assertEqual(data["GLOBAL_BGP_OBSERVATION"], "NOT_OBSERVED_STATIC_DIRECT_PIN")
            self.assertEqual(data["STATUS"], "REVIEW")



if __name__ == "__main__":
    unittest.main()
