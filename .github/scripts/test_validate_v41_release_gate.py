import hashlib
import ipaddress
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from validate_v41_release_gate import (
    REPORT_MARKER, SOURCE_KEYS, check_manifest, format_quality_section,
    inspect_policy, literal_service_exceptions, read_hard_sources,
)


def nets(*rows):
    return {ipaddress.ip_network(x, strict=True) for x in rows}


class ReleaseGateTests(unittest.TestCase):
    def test_protected_hard_exceptions_in_three_classes(self):
        ru = nets("192.0.2.1/32", "192.0.2.2/32", "192.0.2.3/32",
                  "192.0.2.4/32", "2001:db8::1/128")
        hard = [
            (ipaddress.ip_network("192.0.2.1/32"), {"antifilter-ip.lst"}),
            (ipaddress.ip_network("192.0.2.2/32"), {"antifilter-ip.lst"}),
            (ipaddress.ip_network("192.0.2.3/32"), {"antifilter-subnet.lst"}),
            (ipaddress.ip_network("192.0.2.4/32"), {"antifilter-ip.lst"}),
        ]
        result = inspect_policy(
            ru, set(), set(), hard,
            core=nets("192.0.2.1/32"),
            shared=nets("192.0.2.0/30"),
            service=nets("192.0.2.2/32", "192.0.2.3/32", "192.0.2.4/32"))
        v4 = result["families"]["ipv4"]
        classes = v4["classes"]
        self.assertEqual(v4["hard_direct_overridden_addresses"], 4)
        self.assertEqual(v4["unprotected_hard_direct_addresses"], 0)
        for name, count, cidr in (
            ("CORE_CORPORATE", 1, "192.0.2.1/32"),
            ("SHARED_INFRA", 2, "192.0.2.2/31"),
            ("OTHER", 1, "192.0.2.4/32"),
        ):
            with self.subTest(name=name):
                self.assertEqual(classes[name]["addresses"], count)
                self.assertEqual(classes[name]["review_cidrs"], [cidr])
                self.assertIn(f"OBSERVED_HARD_DIRECT {name} {cidr}",
                              format_quality_section(result))
        self.assertEqual(classes["SHARED_INFRA"]["current_antifilter_ip"], 1)
        self.assertEqual(classes["SHARED_INFRA"]["current_antifilter_subnet"], 1)
        self.assertEqual(classes["OTHER"]["current_antifilter_ip"], 1)
        self.assertEqual(classes["OTHER"]["service_protected"], 1)
        self.assertIn(REPORT_MARKER, format_quality_section(result))

    def test_same_count_ip_substitution_changes_exact_class_hash(self):
        def report_for(ip):
            entry = ipaddress.ip_network(f"{ip}/32")
            result = inspect_policy(
                {entry, ipaddress.ip_network("2001:db8::1/128")}, set(), set(),
                [(entry, {"antifilter-ip.lst"})], {entry}, set(), set())
            fields = result["families"]["ipv4"]["classes"]["CORE_CORPORATE"]
            self.assertEqual(fields["addresses"], 1)
            self.assertEqual(fields["review_cidrs"], [str(entry)])
            self.assertEqual(fields["review_cidrs_sha256"],
                             hashlib.sha256((str(entry) + "\n").encode("ascii")).hexdigest())
            self.assertIn(f"OBSERVED_HARD_DIRECT CORE_CORPORATE {entry}",
                          format_quality_section(result))
            return fields["review_cidrs_sha256"]

        self.assertNotEqual(report_for("192.0.2.8"), report_for("192.0.2.9"))

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
            records = read_hard_sources(f)
            self.assertEqual(len(records), 1)
            self.assertIn("antifilter-ip.lst", records[0][1])
            f.write_text("192.0.2.1/32\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing provenance"):
                read_hard_sources(f)

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
