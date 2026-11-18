import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import audit_v41_direct_provenance as audit
import audit_v41_prefix_candidates as review
import report_v41_pr_delta as delta
import v41_cdn_ip_advisory as cdn
from build_v41_overlay import encode_geoip
from v41_reviewed_ipv6_admission import RECORD_KEY, read_reviewed_ipv6_admission

GITHUB = Path(__file__).resolve().parents[1]
FEED = {
    "Akamai": {"asns": ["AS20940"], "ips": ["192.0.2.0/24", "2001:db8:1::/48"]},
    "Fastly": {"asns": [], "ips": ["192.0.2.129/26", "192.0.2.128/26"]},
    "Bunny": {"asns": ["AS1"], "ips": []},
    "BelugaCDN": {"asns": [], "ips": ["198.51.100.1", "2001:db8:2::7"]},
    "Medianova": {"asns": [], "ips": ["2001:db8:1:1::1/64"]},
}


class CdnAdvisoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        catalog = json.loads((GITHUB / "data/v41-audit-global-networks.json").read_bytes())
        catalog["sources"] = [row for row in catalog["sources"]
                              if row["id"] in {"cloudflare-proxy", cdn.SOURCE}]
        self.catalog = self.root / "catalog.json"
        self.catalog.write_text(json.dumps(catalog), encoding="utf-8")

    def snapshot(self, name, response):
        def curl(argv, **kwargs):
            url = argv[-1]
            if url == cdn.URL:
                if isinstance(response, Exception):
                    raise response
                if response is None:
                    return subprocess.CompletedProcess(argv, 22)
                self.assertEqual(kwargs["timeout"], 30)
                payload = response
            else:
                payload = b"203.0.113.0/24\n" if url.endswith("-v4") else b"2001:db8:12::/48\n"
            Path(argv[argv.index("--output") + 1]).write_bytes(payload)
            return subprocess.CompletedProcess(argv, 0)

        path = self.root / (name + ".json.gz")
        with patch.object(audit.subprocess, "run", side_effect=curl):
            audit.collect(self.catalog, path)
        return path

    def test_parser_keeps_per_provider_families_and_reports_normalized_host_bits(self):
        observed = cdn.parse_database(json.dumps(FEED))
        self.assertEqual({n.version for n in observed["Akamai"][0]}, {4, 6})
        self.assertEqual(observed["Fastly"], ({ipaddress.ip_network("192.0.2.128/26")},
                                              {"192.0.2.129/26": "192.0.2.128/26"}))
        self.assertEqual(observed["Bunny"], (set(), {}))
        self.assertEqual(observed["BelugaCDN"], (self.nets("198.51.100.1/32", "2001:db8:2::7/128"), {}))
        self.assertEqual(observed["Medianova"][1], {"2001:db8:1:1::1/64": "2001:db8:1:1::/64"})

    def test_parser_rejects_wrong_shape_duplicate_fields_bad_networks_and_unsafe_labels(self):
        for value in ("[]", "{}", "{} more", '{"x":{"asns":[],"ips":[]},"x":{}}',
                      '{"x":{"asns":[],"ips":"192.0.2.0/24"}}',
                      '{"x|y":{"asns":[],"ips":["192.0.2.0/24"]}}',
                      '{"Bunny":{"asns":[],"ips":[]}}',
                      '{"x":{"asns":[],"ips":["banana/24"]}}',
                      '{"x":{"asns":[],"ips":["0.0.0.0/0"]}}',
                      '{"x":{"asns":[],"ips":["::/0"]}}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cdn.parse_database(value)
        too_many = {f"provider-{i}": {"asns": [], "ips": ["192.0.2.0/24"]}
                    for i in range(cdn.MAX_PROVIDERS + 1)}
        with self.assertRaises(ValueError):
            cdn.parse_database(json.dumps(too_many))
        with self.assertRaisesRegex(ValueError, "CIDR limit"):
            cdn.parse_database(json.dumps({"Provider": {"asns": [], "ips": ["192.0.2.0/24"] * (cdn.MAX_CIDRS + 1)}}))

    def test_capture_binds_payload_and_extends_official_scopes_without_conflating_them(self):
        data = (json.dumps(FEED) + "\n").encode("utf-8")
        path = self.snapshot("available", data)
        metadata, providers = audit.load_snapshot(path)
        self.assertEqual(metadata["files"][cdn.URL]["bytes"], len(data))
        self.assertEqual(metadata["files"][cdn.URL]["sha256"], hashlib.sha256(data).hexdigest())
        self.assertIn("cloudflare-proxy", providers)
        self.assertEqual(providers["cdn-ip-database/Fastly"][0]["owner"], "Fastly")
        info, index = audit.read_cdn_advisory(path)
        self.assertEqual(info["status"], "AVAILABLE")
        self.assertEqual(info["url"], cdn.URL)
        self.assertEqual(info["providers"]["Bunny"]["status"], "UNAVAILABLE")
        self.assertNotIn("Bunny", index)
        self.assertEqual(set(index["Medianova"]), {6})

    def test_capture_fails_open_on_http_timeout_invalid_payload_and_oversize(self):
        for response, reason in (
            (None, "DOWNLOAD_ERROR"),
            (subprocess.TimeoutExpired("curl", 30), "DOWNLOAD_ERROR"),
            (OSError("no output"), "DOWNLOAD_ERROR"),
            (b"<!doctype html>", "INVALID_PAYLOAD"),
            (b"\xff", "INVALID_PAYLOAD"),
            (b"x" * (cdn.MAX_BYTES + 1), "INVALID_SIZE"),
        ):
            with self.subTest(reason=reason):
                path = self.snapshot("unavailable", response)
                info, index = audit.read_cdn_advisory(path)
                self.assertEqual((info["status"], info["reason"], index), ("UNAVAILABLE", reason, {}))
                raw, providers = audit.load_snapshot(path)
                self.assertIsNone(providers[cdn.SOURCE][1])
                self.assertEqual(raw["status"]["cloudflare-proxy"], "AVAILABLE")
                self.assertNotIn(cdn.URL, raw["files"])
        missing = self.root / "absent.gz"
        self.assertEqual(audit.read_cdn_advisory(missing)[0]["status"], "ADVISORY_MISSING")
        missing.write_bytes(b"not gzip")
        self.assertEqual(audit.read_cdn_advisory(missing)[0]["status"], "ADVISORY_MISSING")

    @staticmethod
    def nets(*values):
        return {ipaddress.ip_network(x) for x in values}

    def test_available_and_unavailable_leave_dat_and_srs_byte_identical(self):
        data = json.dumps(FEED).encode()
        available = self.snapshot("available", data)
        unavailable = self.snapshot("unavailable", None)
        table = GITHUB / "data/v41-reviewed-ipv6-admission-exclusions.tsv"
        old, new, sidecar, manifest = [self.root / n for n in ("old.dat", "geoip_RU.dat", "sha", "manifest")]
        before = self.nets("192.0.2.0/25", "2001:db8:1:1::/64")
        after = self.nets("192.0.2.128/25", "2001:db8:1::/48")
        private = self.nets("10.0.0.0/8", "fc00::/7")
        for path, routes in ((old, before), (new, after)):
            path.write_bytes(encode_geoip({"RU": routes, "PRIVATE": private}))
        sidecar.write_text(f"{audit.digest(old.read_bytes())}  geoip_RU.dat\n", encoding="ascii")
        manifest.write_text(json.dumps({
            "output_sha256": audit.digest(new.read_bytes()),
            "input_sha256": {RECORD_KEY: audit.digest(table.read_bytes())},
            RECORD_KEY: {"role": "geography-review-only",
                         "records": list(read_reviewed_ipv6_admission(table).values())},
        }), encoding="utf-8")
        # Real sing-box 1.13.12 SRS bytes compiled from the synthetic candidate and PRIVATE above.
        fixtures = {
            "geoip_RU.srs": "5352530178da626460636480002696030c4c0d20e2bf800223ef0e06980403030354e03f023000020000fffff9580ff9",
            "geoip_PRIVATE.srs": "5352530178da6264606364800026162e06060616aeffffff0bfc614005027fffa3010640000000ffff47ba152d",
        }
        for name, payload in fixtures.items():
            (self.root / name).write_bytes(bytes.fromhex(payload))
        assets = {p: p.read_bytes() for p in (new, manifest, *(self.root / n for n in fixtures))}
        candidates = self.root / "candidates.tsv"
        candidates.write_text("\t".join(review.HEADER) + "\n" +
            "192.0.2.0/24\tAS20940\tFixture\t2025-01-01\t2027-01-01"
            "\thttps://example.test/bgp\thttps://example.test/rdap\n", encoding="utf-8")

        publications, reviews = [], []
        for path in (available, unavailable, self.root / "missing.gz"):
            provider_snapshot = path if path.exists() else None
            publications.append(delta.exact_delta(new, old, sidecar, manifest, table, "a" * 40,
                                                   provider_snapshot=provider_snapshot))
            output = self.root / "review.json"
            subprocess.run([sys.executable, str(Path(review.__file__)), "--dat", str(new),
                            "--candidates", str(candidates), "--provider-snapshot", str(path),
                            "--output", str(output)], check=True, capture_output=True)
            reviews.append(json.loads(output.read_bytes()))
            self.assertEqual({p: p.read_bytes() for p in assets}, assets)
        populated, failed, missing = publications
        for report in (failed, missing):
            self.assertEqual(report["direct"], populated["direct"])
            self.assertEqual(report["private_changed"], populated["private_changed"])
            self.assertIsNone(report["cdn_ip_database"]["delta_overlaps"])
        matches = {r["provider"]: r for r in populated["cdn_ip_database"]["delta_overlaps"]}
        self.assertEqual(matches["Akamai"]["ipv4"]["added"]["addresses"], "128")
        self.assertEqual(matches["Akamai"]["ipv4"]["removed"]["addresses"], "128")
        self.assertIn("2001:db8:1::/64", matches["Akamai"]["ipv6"]["added"]["cidrs"])
        self.assertEqual(matches["Fastly"]["ipv4"]["added"]["cidrs"], ["192.0.2.128/26"])
        self.assertNotIn("ipv6", matches["Fastly"])
        self.assertNotIn("Bunny", matches)
        self.assertIn("| Fastly | +64 / −0 | Unknown |", delta.cdn_summary(populated["cdn_ip_database"]))
        self.assertEqual([r["cdn_ip_database"]["status"] for r in reviews],
                         ["AVAILABLE", "UNAVAILABLE", "ADVISORY_MISSING"])
        row = reviews[0]["candidates"][0]
        self.assertEqual(row["direct_addresses"], "128")
        self.assertEqual([(x["provider"], x["addresses"]) for x in row["cdn_ip_database_overlaps"]],
                         [("Akamai", "256"), ("Fastly", "64")])
        self.assertIsNone(reviews[1]["candidates"][0]["cdn_ip_database_overlaps"])

        # The global provenance view carries the exact same provider labels alongside official scopes.
        _, providers = audit.load_snapshot(available)
        report = audit.build_report(old, new, providers, {"v37-base": after}, private)
        entries = report["providers"]
        self.assertEqual(entries["cdn-ip-database/Akamai"]["role"], cdn.ROLE)
        self.assertEqual(entries["cdn-ip-database/Fastly"]["families"]["4"]["added"], "64")
        self.assertNotIn("6", entries["cdn-ip-database/Fastly"]["families"])
        self.assertEqual(entries["cdn-ip-database/Bunny"]["status"], "UNAVAILABLE")
        self.assertTrue(any(r["provider_name"] == "Medianova" and r["advisory_source"] == cdn.SOURCE
                            for r in report["rows"]))
        self.assertEqual({p: p.read_bytes() for p in assets}, assets)

    def test_feed_is_not_a_build_input_and_runs_only_as_a_pr_advisory(self):
        inputs = (GITHUB / "data/v41-upstream-sources.json").read_text(encoding="utf-8")
        workflow = (GITHUB / "workflows/geoip-v41.yml").read_text(encoding="utf-8")
        self.assertNotIn(cdn.SOURCE, inputs)
        capture = workflow.split("- name: Capture scoped provider feeds (advisory)", 1)[1].split("- name:", 1)[0]
        self.assertIn("if: github.event_name == 'pull_request'", capture)
        self.assertIn("continue-on-error: true", capture)
        self.assertNotIn("provider-snapshot", workflow.split("\n  publish:", 1)[1])


if __name__ == "__main__":
    unittest.main()
