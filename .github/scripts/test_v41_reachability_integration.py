"""Exercise the candidate builder and independent validator on synthetic inputs."""
import ipaddress
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import build_v41_overlay as builder
import validate_v41_overlay as validator
from v41_reviewed_ipv6_admission import HEADER as IPV6_HEADER
from v41_reviewed_unreachable import read_reviewed
from validate_v41_telegram import PINNED_FEED


class ReachabilityIntegrationTests(unittest.TestCase):
    def test_builder_and_validator_preserve_core_and_ignore_country_alone(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            def write(name, content):
                path = root / name
                path.write_text(content, encoding="utf-8")
                return path
            def dat(name, categories):
                path = root / name
                path.write_bytes(builder.encode_geoip({
                    name: {ipaddress.ip_network(x) for x in entries}
                    for name, entries in categories.items()
                }))
                return path
            base = dat("base.dat", {"RU": ["11.0.0.0/24", "12.0.0.0/24", "13.0.0.0/24",
                                            "2001:4860:1234::/48", "2001:4860:5678::/48", "2001:4860:aa::/48"],
                                    "PRIVATE": ["10.0.0.0/8", "fc00::/7"]})
            hydra = dat("hydra.dat", {"DIRECT": ["12.0.0.0/24"], "WHITELIST": ["19.0.0.1/32"]})
            rir = write("rir.tsv", "country\tprefix\tregistry\tstatus\nRU\t11.0.0.0/24\tripencc\tallocated\nBY\t16.0.0.0/24\tripencc\tallocated\nKZ\t17.0.0.0/24\tripencc\tallocated\n")
            geo = write("geo.tsv", "prefix\tdelegated_country\tassignment_country\torigin_asn\tchecked_on\n11.0.0.0/25\tRU\tUS\tAS123\t2026-11-13\n")
            geo6 = write("geo6.tsv", "\t".join(IPV6_HEADER) + "\n"
                         "2001:4860:1234::/48\tAS123\tDE\tselected_origin_ASN\t2026-11-15\t"
                         "https://rdap.db.ripe.net/ip/2001:4860:1234::/48\thttps://example.test/geofeed.csv\n")
            operator = write("operator.tsv", "country\tprefix\torigin_asn\nRU\t23.0.0.0/24\tAS123\n")
            unreachable = write("unreachable.tsv", "cidr\tkind\tevidence\tverified_on\treview_after\n"
                                "12.0.0.0/25\tIP_LAYER_BLOCK\thttps://example.test/a\t2020-01-01\t2099-01-01\n"
                                "13.0.0.0/25\tINBOUND_GEO_IP_BLOCK\thttps://example.test/b\t2020-01-01\t2099-01-01\n"
                                "2001:4860:5678::/48\tIP_LAYER_BLOCK\thttps://example.test/c\t2020-01-01\t2099-01-01\n"
                                "2001:4860:aa::/48\tIP_LAYER_BLOCK\thttps://example.test/d\t2020-01-01\t2099-01-01\n")
            services = [{"name": str(i), "tier": "standard", "ipv4": ["18.0.0.1/32"], "ipv6": [], "domains": 0} for i in range(50)]
            service_json = write("services.json", json.dumps({"categories": [{"id": "test", "services": services}]}))
            files = {
                "base": base, "hydra": hydra, "rir": rir,
                "kyoresuas-v4": write("ky4", "18.0.0.1/32\n"),
                "kyoresuas-v6": write("ky6", "2001:4860:4860::8888/128\n"),
                "kyoresuas-services": service_json,
                "w1zardz": write("w1", "19.0.0.1/32\n"),
                "hxehex-ip": write("hxe", "24.0.0.1/32\n"),
                "escapingworm": write("escape", "20.0.0.1/32\n"),
                "blocked-base": write("blocked", "13.0.0.129/32\n22.0.0.1/32\n"),
                "blocked-exact": write("exact", "13.0.0.129/32\n"),
                "blocked-resolved": write("resolved", "22.0.0.1/32\n"),
                "company-prefixes": write("company", "13.0.0.0/24\n14.0.0.0/24\n2001:4860:aa::/48\n"),
                "core-company-prefixes": write("core", "13.0.0.0/24\n2001:4860:aa::/48\n"),
                "shared-infrastructure-prefixes": write("shared", "14.0.0.0/24\n"),
                "regional-origin-prefixes": write("origins", "15.0.0.0/24\n"),
                "reviewed-operator-prefixes": operator, "regional-admission-exclusions": geo,
                "reviewed-ipv6-admission-exclusions": geo6, "ipsum": write("ipsum", "# diagnostic empty\n"),
                "telegram-feed": PINNED_FEED,
            }
            outputs = {name: root / name for name in ("output", "categories", "quality", "metrics", "prefix-provenance", "blocked-provenance", "blocked-output", "manifest")}
            argv = ["build_v41_overlay.py"]
            for key, value in (files | outputs).items():
                argv.extend(("--" + key, str(value)))
            records = read_reviewed(unreachable)
            with patch.object(builder, "UNREACHABLE_PATH", unreachable), patch.object(builder, "read_unreachable", return_value=records), patch.object(sys, "argv", argv):
                self.assertEqual(builder.main(), 0)
            result = builder.parse_geoip_dat(outputs["output"])["RU"]
            contains = lambda addr: any(ipaddress.ip_address(addr) in net for net in result)
            self.assertTrue(contains("11.0.0.1"), "foreign registration alone must not remove a regional address")
            self.assertFalse(contains("12.0.0.1"), "reviewed IP-layer exclusion applies outside core")
            self.assertTrue(contains("12.0.0.200"), "neighboring addresses must remain")
            self.assertTrue(contains("13.0.0.1"), "core company is protected from the new exclusion")
            self.assertFalse(contains("13.0.0.129"), "existing hard evidence must still win")
            self.assertTrue(contains("2001:4860:1234::1"), "foreign IPv6 assignment alone must not carve")
            self.assertFalse(contains("2001:4860:5678::1"), "unprotected IPv6 is subject to reviewed exclusions")
            self.assertTrue(contains("2001:4860:aa::1"), "IPv6 core company is protected")
            args = SimpleNamespace(
                geoip=outputs["output"], base=base, hydra=hydra, blocked_union=files["blocked-base"],
                blocked_exact=files["blocked-exact"], blocked_resolved=files["blocked-resolved"],
                company_all=files["company-prefixes"], company_core=files["core-company-prefixes"],
                company_shared=files["shared-infrastructure-prefixes"], regional_origin_prefixes=files["regional-origin-prefixes"],
                kyoresuas_v4=files["kyoresuas-v4"], kyoresuas_v6=files["kyoresuas-v6"], kyoresuas_services=service_json,
                w1zardz=files["w1zardz"], hxehex_ip=files["hxehex-ip"], escapingworm=files["escapingworm"],
                effective_blocked=outputs["blocked-output"], ipsum=files["ipsum"], manifest=outputs["manifest"],
                quality=outputs["quality"], rir=rir, regional_admission_exclusions=geo,
                reviewed_operator_prefixes=operator, reviewed_ipv6_admission_exclusions=geo6, telegram_feed=PINNED_FEED,
            )
            with patch.object(validator, "UNREACHABLE_PATH", unreachable), patch.object(validator, "read_reviewed", return_value=records):
                self.assertEqual(validator.validate(args)["status"], "VALID")
                original = outputs["output"].read_bytes()
                original_manifest = outputs["manifest"].read_text(encoding="utf-8")
                categories = builder.parse_geoip_dat(outputs["output"])
                categories["RU"].add(ipaddress.ip_network("12.0.0.0/25"))
                tampered = builder.encode_geoip(categories)
                outputs["output"].write_bytes(tampered)
                manifest = json.loads(original_manifest)
                manifest["output_sha256"] = hashlib.sha256(tampered).hexdigest()
                outputs["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "DIRECT intersects"):
                    validator.validate(args)
                outputs["output"].write_bytes(original)
                outputs["manifest"].write_text(original_manifest, encoding="utf-8")
