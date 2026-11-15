import hashlib
import ipaddress
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import build_v41_overlay as builder
from validate_v41_overlay import verify_ipv6_admission_effect
from v41_reviewed_ipv6_admission import (
    HEADER,
    RECORD_KEY,
    read_reviewed_ipv6_admission,
    verify_reviewed_ipv6_admission_manifest,
)

DATA = Path(__file__).resolve().parent.parent / "data/v41-reviewed-ipv6-admission-exclusions.tsv"
KP = ipaddress.ip_network("2a0b:4e07:63f0::/48")
IN = ipaddress.ip_network("2a0b:4e07:63f1::/48")
NL = ipaddress.ip_network("2a0b:4e07:6300::/48")
DE = ipaddress.ip_network("2a0b:4e07:6310::/48")
RU = ipaddress.ip_network("2a0b:4e07:6301::/48")
ANYCAST = ipaddress.ip_network("2a0b:4e07:63ff::/48")


class ReviewedIPv6AdmissionTests(unittest.TestCase):
    def test_production_records_are_the_individually_reviewed_routes(self):
        records = read_reviewed_ipv6_admission(DATA)
        self.assertEqual({p: r["assignment_country"] for p, r in records.items()},
                         {KP: "KP", IN: "IN", NL: "NL", DE: "DE"})
        self.assertTrue(all(r["origin_asn"] == "AS218750" for r in records.values()))

    def test_exact_exclusion_preserves_both_sides_and_other_families(self):
        parent = ipaddress.ip_network("2a0b:4e07:63f0::/46")
        before = {parent, ipaddress.ip_network("2a0b:4e07:6301::/48"),
                  ipaddress.ip_network("192.0.2.0/24")}
        result = builder.subtract_networks(before, {KP})
        self.assertEqual(result, before - {parent} | set(parent.address_exclude(KP)))
        self.assertIn(IN, result)
        with self.assertRaisesRegex(ValueError, "IPv6 DIRECT intersects"):
            builder.assert_regional_admission_disjoint(result, {KP, IN})
        builder.assert_regional_admission_disjoint(
            builder.subtract_networks(result, {IN}), {KP, IN}
        )

    def test_production_exclusions_split_nl_ru_aggregate_and_preserve_anycast(self):
        records = read_reviewed_ipv6_admission(DATA)
        before = {NL.supernet(), KP.supernet(), DE, ANYCAST}
        self.assertEqual(builder.subtract_networks(before, records), {RU, ANYCAST})
        self.assertEqual(
            verify_ipv6_admission_effect({RU, ANYCAST}, before, set(), set(), {}, records),
            4 * NL.num_addresses,
        )

    def test_invalid_rows_do_not_widen_or_obscure_the_mask(self):
        good = next(line for line in DATA.read_text(encoding="utf-8").splitlines()
                    if line.startswith(f"{KP}\t"))
        for row in (
            good.replace("/48", "/47"), good.replace("/48", "/49"),
            good.replace(str(KP), "8.8.8.0/24"),
            good.replace(str(KP), "ff0e:1::/48"),
            good.replace(str(KP), "fec0::/48"),
            good.replace(str(KP), "fd00::/48"),
            good.replace(str(KP), "2a0b:4e07:63f0::1/48"),
            good.replace(str(KP), "2A0B:4E07:63F0::/48"),
            good.replace("AS218750", "AS0"), good.replace("AS218750", "AS4294967296"),
            good.replace("\tKP\t", "\tRU\t"),
            good.replace("selected_origin_ASN", "whole_ASN"),
            good.replace("2026-11-15", "2026-11-31"),
            good.replace("/ip/", "/autnum/"),
            good.replace("https://raw", "http://raw"),
            good.replace("https://raw", "https://name@raw"),
            good.replace("geofeed.csv", "geofeed.csv#fragment"),
            good + "\textra", good + "\n" + good,
        ):
            with self.subTest(row=row), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "exceptions.tsv"
                path.write_text("\t".join(HEADER) + "\n" + row + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "invalid reviewed IPv6 admission"):
                    read_reviewed_ipv6_admission(path)

    def test_manifest_binds_exact_bytes_and_rows(self):
        records = read_reviewed_ipv6_admission(DATA)
        expected = {"input_sha256": {RECORD_KEY: hashlib.sha256(DATA.read_bytes()).hexdigest()},
                    RECORD_KEY: {"records": list(records.values())}}
        self.assertEqual(verify_reviewed_ipv6_admission_manifest(DATA, expected), records)
        for wrong in ({}, {**expected, RECORD_KEY: {"records": []}},
                      {**expected, "input_sha256": {RECORD_KEY: "0" * 64}}):
            with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                verify_reviewed_ipv6_admission_manifest(DATA, wrong)

    def test_header_only_is_explicit_noop_but_missing_header_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "exceptions.tsv"
            path.write_text("\t".join(HEADER) + "\n", encoding="utf-8")
            self.assertEqual(read_reviewed_ipv6_admission(path), {})
            path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid reviewed IPv6 admission header"):
                read_reviewed_ipv6_admission(path)


    def test_independent_delta_detects_missing_neighbors_and_counts_only_live_coverage(self):
        domain = {ipaddress.ip_network("2a0b:4e07:63f0::/46")}
        hard = {IN}
        with_rules = builder.subtract_networks(domain, {KP, IN})
        self.assertEqual(
            verify_ipv6_admission_effect(with_rules, domain, set(), hard, {}, {KP, IN}),
            KP.num_addresses,
        )
        with self.assertRaisesRegex(ValueError, "outside the expected exact output"):
            verify_ipv6_admission_effect(set(), domain, set(), hard, {}, {KP, IN})

    def test_prepublication_rejects_leak_even_with_matching_manifest_and_dat_digest(self):
        script = Path(__file__).with_name("v41_reviewed_ipv6_admission.py").resolve()
        records = read_reviewed_ipv6_admission(DATA)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            dat, manifest = p / "geoip.dat", p / "manifest.json"
            for network, return_code in ((RU, 0), (ANYCAST, 0), (KP, 1), (NL, 1), (DE, 1)):
                with self.subTest(network=network):
                    blob = builder.encode_geoip({
                        "RU": {network},
                        "PRIVATE": {ipaddress.ip_network("fc00::/7")},
                    })
                    dat.write_bytes(blob)
                    manifest.write_text(json.dumps({
                        "output_sha256": hashlib.sha256(blob).hexdigest(),
                        "input_sha256": {RECORD_KEY: hashlib.sha256(DATA.read_bytes()).hexdigest()},
                        RECORD_KEY: {"records": list(records.values())},
                    }), encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, str(script), "--table", str(DATA),
                         "--manifest", str(manifest), "--geoip", str(dat)],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, return_code, result.stderr)
                    if return_code:
                        self.assertIn("IPv6 DIRECT intersects", result.stderr)
