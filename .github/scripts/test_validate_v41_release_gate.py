import hashlib
import ipaddress
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from validate_v41_release_gate import (
    REPORT_MARKER, SOURCE_KEYS, check_manifest, format_quality_section,
    inspect_policy, literal_service_exceptions, read_hard_sources, verify_hard_evidence,
)


def nets(*rows):
    return {ipaddress.ip_network(x, strict=True) for x in rows}


class ReleaseGateTests(unittest.TestCase):
    def test_confirmed_ip_blocks_win_over_every_direct_protection_class(self):
        ru = nets("192.0.2.1/32", "2001:db8::1/128")
        for role in ("core", "shared", "service"):
            for host in ru:
                with self.subTest(role=role, version=host.version):
                    masks = {key: {host} if key == role else set() for key in ("core", "shared", "service")}
                    with self.assertRaisesRegex(ValueError, "unprotected hard-block leak"):
                        inspect_policy(ru, set(), set(), [(host, {"reviewed-rkn-ip-record"})], **masks)

    def test_unprotected_hard_direct_fails_even_if_shared(self):
        ru = nets("192.0.2.4/32", "2001:db8::1/128")
        shared = nets("192.0.2.0/24", "2001:db8::/64")
        for host in sorted(ru, key=lambda net: net.version):
            with self.subTest(version=host.version):
                with self.assertRaisesRegex(ValueError, f"^IPv{host.version} unprotected hard-block leak"):
                    inspect_policy(ru, set(), set(), [(host, {"antifilter-ip.lst"})],
                                   set(), shared, set())

    def test_gate_rejects_a_subnet_in_hard_service_exceptions(self):
        ru = nets("192.0.2.4/32", "2001:db8::1/128")
        with self.assertRaisesRegex(ValueError, "literal host"):
            inspect_policy(
                ru, set(), set(), [(ipaddress.ip_network("192.0.2.4/32"), {"antifilter-ip.lst"})],
                set(), set(), nets("192.0.2.0/24"),
            )

    def test_gate_reconstructs_literal_service_hosts_from_sources(self):
        regions = {"RU": nets("192.0.2.1/32", "192.0.2.4/31"), "BY": nets("198.51.100.1/32")}
        sources = {
            "w1zardz-service-direct": nets("192.0.2.0/30", "192.0.2.4/32", "198.51.100.1/32"),
            "kyoresuas-standard": nets("192.0.2.8/32", "192.0.2.10/31"),
            "hxehex-mobile-hosts": nets("2001:db8::6/128"),
            "operator-whitelist": nets("192.0.2.9/32"),
        }
        self.assertEqual(
            literal_service_exceptions(regions, sources),
            nets("192.0.2.4/32", "192.0.2.8/32", "2001:db8::6/128"),
        )

    def test_effective_and_private_precedence_are_fatal(self):
        ru = nets("192.0.2.1/32", "2001:db8::1/128")
        for host in sorted(ru, key=lambda net: net.version):
            protected = {host}
            hard = [(host, {"antifilter-ip.lst"})]
            for private, effective, mask in (
                (protected, set(), "PRIVATE"),
                (set(), protected, "effective blocked set"),
            ):
                with self.subTest(version=host.version, mask=mask):
                    with self.assertRaisesRegex(
                            ValueError, f"^IPv{host.version} DIRECT intersects {mask}$"):
                        inspect_policy(ru, private, effective, hard, protected, set(), set())

    def test_hard_sources_require_provenance(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "hard.txt"
            f.write_text("192.0.2.1/32 # sources=antifilter-ip.lst,v38-baseline-hard-or-unclassified\n",
                         encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-IP or unknown evidence"):
                read_hard_sources(f)
            f.write_text("192.0.2.1/32 # sources=reviewed-rkn-ip-record\n")
            self.assertEqual(len(read_hard_sources(f)), 1)
            f.write_text("192.0.2.1/32\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing provenance"):
                read_hard_sources(f)

    def test_gate_rebuilds_hard_sources_and_rejects_missing_or_injected_cidr(self):
        from prepare_blocked_sources_v41 import TELEGRAM_PREFIXES
        with tempfile.TemporaryDirectory() as t:
            subnet = Path(t) / "subnet.lst"
            registry = Path(t) / "reviewed.tsv"
            subnet.write_text("192.0.2.0/24\n198.0.0.0/8\n")
            registry.write_text(
                "CIDR\tKIND\tCHECKED_ON\tEVIDENCE\n"
                "203.0.113.1/32\tDIRECT_IP_OR_SUBNET\t2026-11-13\thttps://blocklist.rkn.gov.ru/example\n"
            )
            rows = [(ipaddress.ip_network(p), {"runetfreedom-static-telegram"}) for p in TELEGRAM_PREFIXES]
            rows += [(ipaddress.ip_network("192.0.2.0/24"), {"antifilter-subnet.lst"}),
                     (ipaddress.ip_network("203.0.113.1/32"), {"reviewed-rkn-ip-record"})]
            verify_hard_evidence(rows, subnet, registry)
            for tampered in (rows[:-1], rows + [(ipaddress.ip_network("192.0.3.0/24"), {"antifilter-subnet.lst"})]):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    verify_hard_evidence(tampered, subnet, registry)

    def test_manifest_verifies_the_current_inputs(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            args = SimpleNamespace()
            for name in ("geoip", *SOURCE_KEYS):
                file = root / (name + ".txt")
                file.write_text(name, encoding="utf-8")
                setattr(args, name, file)
            manifest = {"schema": 2,
                        "output_sha256": hashlib.sha256(b"geoip").hexdigest(),
                        "input_sha256": {
                            key: hashlib.sha256(field.encode()).hexdigest()
                            for field, key in SOURCE_KEYS.items()
                        }}
            check_manifest(manifest, args)
            args.core.write_text("modified", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "corporate_core_prefixes"):
                check_manifest(manifest, args)


if __name__ == "__main__":
    unittest.main()
