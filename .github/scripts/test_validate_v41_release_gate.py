import hashlib
import ipaddress
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from validate_v41_release_gate import (
    REPORT_MARKER, SOURCE_KEYS, check_manifest, format_quality_section,
    inspect_policy, read_hard_sources,
)


def nets(*rows):
    return {ipaddress.ip_network(x, strict=True) for x in rows}


class ReleaseGateTests(unittest.TestCase):
    def test_protected_hard_exceptions_in_three_classes(self):
        ru = nets("192.0.2.1/32", "192.0.2.2/32", "192.0.2.3/32")
        hard = [
            (ipaddress.ip_network("192.0.2.1/32"), {"antifilter-ip.lst"}),
            (ipaddress.ip_network("192.0.2.2/32"), {"antifilter-ip.lst"}),
            (ipaddress.ip_network("192.0.2.3/32"), {"antifilter-subnet.lst"}),
        ]
        result = inspect_policy(
            ru, set(), set(), hard,
            core=nets("192.0.2.1/32"),
            shared=nets("192.0.2.0/30"),
            service=nets("192.0.2.2/32", "192.0.2.3/32"))
        v4 = result["families"]["ipv4"]
        self.assertEqual(v4["hard_direct_overridden_addresses"], 3)
        self.assertEqual(v4["unprotected_hard_direct_addresses"], 0)
        self.assertEqual(v4["classes"]["CORE_CORPORATE"]["addresses"], 1)
        self.assertEqual(v4["classes"]["SHARED_INFRA"]["addresses"], 2)
        self.assertEqual(v4["classes"]["SHARED_INFRA"]["current_antifilter_ip"], 1)
        self.assertEqual(v4["classes"]["SHARED_INFRA"]["current_antifilter_subnet"], 1)
        self.assertIn(REPORT_MARKER, format_quality_section(result))

    def test_unprotected_hard_direct_fails_even_if_shared(self):
        with self.assertRaisesRegex(ValueError, "unprotected hard-block leak"):
            inspect_policy(
                nets("192.0.2.4/32"), set(), set(),
                [(ipaddress.ip_network("192.0.2.4/32"), {"antifilter-ip.lst"})],
                set(), nets("192.0.2.0/24"), set())

    def test_effective_and_private_precedence_are_fatal(self):
        host = nets("192.0.2.1/32")
        for private, effective in [(host, set()), (set(), host)]:
            with self.subTest(private=bool(private)):
                with self.assertRaises(ValueError):
                    inspect_policy(host, private, effective, [], set(), set(), set())

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
