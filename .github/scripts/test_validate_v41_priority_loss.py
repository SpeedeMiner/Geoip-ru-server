import ipaddress
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import validate_v41_priority_loss as gate


def nets(*rows):
    return {ipaddress.ip_network(row) for row in rows}


class PriorityLossTests(unittest.TestCase):
    def test_candidate_inputs_are_bound_to_manifest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dat, origins, rir, company, manifest = (root / x for x in ("dat", "origins", "rir", "company", "manifest"))
            dat.write_bytes(b"candidate")
            origins.write_bytes(b"origin snapshot")
            rir.write_bytes(b"regional snapshot")
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            company.write_text(f"# selected_origin_input_sha256={digest(origins)}\n", encoding="utf-8")
            manifest.write_text(json.dumps({"output_sha256": digest(dat), "input_sha256": {
                "regional_rir_inventory": digest(rir), "corporate_company_asn_origin_prefixes": digest(company)}}), encoding="utf-8")
            gate.verify_binding(manifest, dat, origins, rir, company)
            origins.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "selected ASN input"):
                gate.verify_binding(manifest, dat, origins, rir, company)

    def test_removed_space_is_not_hidden_by_equal_size_addition(self):
        old = {"AS123": nets("192.0.2.0/24", "2001:db8::/120")}
        new = {"AS123": nets("192.0.3.0/24", "2001:db8::/121")}
        rows = gate.compare(old, new)
        self.assertEqual(rows[0]["removed"], "256")
        self.assertTrue(rows[0]["needs_review"])
        self.assertEqual(rows[1]["removed"], "128")
        self.assertTrue(rows[1]["needs_review"])

    def test_missing_baseline_never_passes_as_zero_loss(self):
        rows = gate.compare({"AS123": set()}, {"AS123": nets("192.0.2.0/24")})
        self.assertTrue(rows[-1]["needs_review"])
        self.assertIn("no baseline", rows[-1]["reason"])
        with self.assertRaisesRegex(ValueError, "requires exact candidate SHA"):
            gate.enforce(rows, "a" * 64, "b" * 64)
        gate.enforce(rows, "a" * 64, "a" * 64)

    def test_missing_ipv6_baseline_is_reported_not_a_coverage_claim(self):
        old = {"AS123": nets("192.0.2.0/24")}
        new = {"AS123": nets("192.0.2.0/24")}
        rows = gate.compare(old, new)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[1]["status"], "no-baseline")
        self.assertFalse(rows[1]["needs_review"])

    def test_parses_priority_origins_and_rir(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            asns, origins, rir = root / "asns", root / "origins", root / "rir"
            asns.write_text("AS123 # label\n", encoding="utf-8")
            origins.write_text("192.0.2.0/24 # AS123[company],AS456[other]\n", encoding="utf-8")
            rir.write_text("country\tprefix\tregistry\tstatus\nRU\t192.0.2.0/24\tripencc\tallocated\n", encoding="utf-8")
            self.assertEqual(gate.read_origins(origins, gate.read_asns(asns))["AS123"], nets("192.0.2.0/24"))
            self.assertEqual(gate.read_regions(rir)["RU"], nets("192.0.2.0/24"))
