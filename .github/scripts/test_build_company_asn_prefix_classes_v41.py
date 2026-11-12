import tempfile
import unittest
from pathlib import Path

from build_company_asn_prefix_classes_v40 import build_company_prefix_classes


class CompanyASNPrefixClassTests(unittest.TestCase):
    def make_inputs(self, root: Path):
        registry = root / "registry.tsv"
        policy = root / "policy.tsv"
        selected = root / "selected.tsv"
        rows = [
            f"AS{asn}\tGroup{asn}\tCompany {asn}\thttps://example.test/AS{asn}"
            for asn in range(100, 112)
        ]
        registry.write_text("\n".join(rows) + "\n", encoding="utf-8")
        policy_rows = ["ASN\tEXCEPTION_CLASS\tCOMPANY_GROUP\tPOLICY_NOTE"]
        for asn in range(100, 112):
            role = "CORE_CORPORATE" if asn < 106 else "SHARED_INFRA"
            policy_rows.append(f"AS{asn}\t{role}\tGroup{asn}\tfixture")
        policy.write_text("\n".join(policy_rows) + "\n", encoding="utf-8")
        selected.write_text(
            "# exact selected origin snapshot\n"
            "198.51.100.0/24 # AS100[Group100],AS64500[RIR-RU]\n"
            "203.0.113.0/24 # AS106[Group106],AS64501[RIR-RU]\n"
            "192.0.2.0/24 # AS100[Group100],AS106[Group106]\n"
            "2001:db8:100::/48 # AS111[Group111]\n"
            "2001:db8:200::/48 # AS64500[RIR-RU]\n",
            encoding="utf-8",
        )
        return registry, policy, selected

    def test_core_shared_and_all_masks_are_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, policy, selected = self.make_inputs(root)
            all_out, core_out, shared_out = root / "all.txt", root / "core.txt", root / "shared.txt"
            result = build_company_prefix_classes(selected, registry, policy, all_out, core_out, shared_out)
            all_text = all_out.read_text(encoding="utf-8")
            core_text = core_out.read_text(encoding="utf-8")
            shared_text = shared_out.read_text(encoding="utf-8")
            self.assertEqual(result["all_company_origins"]["prefixes"], 4)
            self.assertIn("198.51.100.0/24 # AS100", core_text)
            self.assertIn("192.0.2.0/24 # AS100", core_text)
            self.assertNotIn("192.0.2.0/24", shared_text)
            self.assertIn("203.0.113.0/24 # AS106", shared_text)
            self.assertIn("2001:db8:100::/48 # AS111", shared_text)
            self.assertIn("198.51.100.0/24", all_text)
            self.assertNotIn("2001:db8:200::/48", all_text)

    def test_moas_core_precedence_prevents_shared_downgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, policy, selected = self.make_inputs(root)
            all_out, core_out, shared_out = root / "all.txt", root / "core.txt", root / "shared.txt"
            build_company_prefix_classes(selected, registry, policy, all_out, core_out, shared_out)
            self.assertIn("192.0.2.0/24", core_out.read_text(encoding="utf-8"))
            self.assertNotIn("192.0.2.0/24", shared_out.read_text(encoding="utf-8"))

    def test_registry_policy_must_match_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, policy, selected = self.make_inputs(root)
            policy.write_text(policy.read_text(encoding="utf-8").replace("AS111\tSHARED_INFRA", "AS999\tSHARED_INFRA"), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_company_prefix_classes(selected, registry, policy, root/"all", root/"core", root/"shared")

    def test_unknown_exception_class_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, policy, selected = self.make_inputs(root)
            policy.write_text(policy.read_text(encoding="utf-8").replace("CORE_CORPORATE", "DIRECT_EVERYTHING", 1), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_company_prefix_classes(selected, registry, policy, root/"all", root/"core", root/"shared")


if __name__ == "__main__":
    unittest.main()
