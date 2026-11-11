import argparse
import csv
import ipaddress
import json
import pathlib
import tempfile
import unittest

import home_probe_ingest


class HomeProbeIngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.report = self.root / "report"
        self.report.mkdir()
        self.targets_path = self.root / "targets.json"
        self.inventory_path = self.root / "inventory.tsv"
        self.output = self.root / "ingest"
        self.write_targets()
        self.write_inventory()
        self.write_report()

    def tearDown(self):
        self.temp.cleanup()

    def write_targets(self):
        self.targets_path.write_text(json.dumps({
            "schema_version": 1,
            "countries": ["RU", "KZ", "BY"],
            "targets": [{
                "id": "ru-example",
                "domain": "example.ru",
                "role": "service",
                "country_scope": ["RU", "KZ"],
                "port": 443,
                "path": "/",
            }],
        }), encoding="utf-8")

    def write_inventory(self):
        with self.inventory_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
            writer.writerow(["CATEGORY", "PREFIX", "FAMILY", "ADDRESS_COUNT"])
            writer.writerow(["RU", "5.143.108.0/22", "IPv4", 1024])
            writer.writerow(["RU", "8.8.8.0/24", "IPv4", 256])
            writer.writerow(["PRIVATE", "10.0.0.0/8", "IPv4", 16777216])

    def write_report(self, source_ip="5.143.110.119", country="RU", required_country="RU"):
        source = {
            "schema_version": 1,
            "observations": [
                {"provider": "ipwho.is", "ip": source_ip, "country": country, "asn": 12389, "organization": "Example ISP"},
                {"provider": "ipapi.co", "ip": source_ip, "country": country, "asn": 12389, "organization": "Example ISP"},
            ],
            "errors": [],
            "verified": True,
            "status": "TWO_SOURCE_CONSENSUS",
            "public_ip": source_ip,
            "country": country,
            "asn_candidates": [12389],
            "organizations": ["Example ISP"],
            "required_country": required_country,
            "required_country_matches": country == required_country,
        }
        summary = {
            "schema_version": 1,
            "probe_type": "USER_CONTROLLED_HOME_OR_ACCESS_NETWORK",
            "required_country": required_country,
            "source_attribution_status": "TWO_SOURCE_CONSENSUS",
            "source_ip_verified_by_two_services": True,
            "source_public_ip": source_ip,
            "source_country": country,
            "source_asn_candidates": [12389],
            "source_organizations": ["Example ISP"],
            "proxy_environment_variables": [],
            "proxy_environment_clear": True,
            "target_count": 1,
            "service_targets": 1,
            "control_targets": 0,
            "automatic_upload": False,
            "geoip_mutation": False,
        }
        measurement = {
            "observed_at": "2026-11-11T06:00:00Z",
            "source": "user_controlled_home_probe",
            "target_id": "ru-example",
            "target_domain": "example.ru",
            "target_role": "service",
            "dns_ipv4_status": "DNS_ANSWER",
            "dns_ipv4_addresses": ["8.8.8.8", "1.1.1.1"],
            "dns_ipv4_error": "",
            "https_ipv4_tested_address": "8.8.8.8",
            "https_ipv4_result": "HTTP_RESPONSE",
            "https_ipv4_status": 403,
            "https_ipv4_error": "",
            "dns_ipv6_status": "DNS_ANSWER",
            "dns_ipv6_addresses": ["2001:4860:4860::8888"],
            "dns_ipv6_error": "",
            "https_ipv6_tested_address": "2001:4860:4860::8888",
            "https_ipv6_result": "INCONCLUSIVE",
            "https_ipv6_status": None,
            "https_ipv6_error": "no route",
        }
        (self.report / "home_probe_source.json").write_text(
            json.dumps(source), encoding="utf-8"
        )
        (self.report / "home_probe_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        (self.report / "home_probe_measurements.jsonl").write_text(
            json.dumps(measurement) + "\n", encoding="utf-8"
        )

    def args(self, required_country="RU"):
        return argparse.Namespace(
            report_dir=str(self.report),
            inventory=str(self.inventory_path),
            targets=str(self.targets_path),
            output_dir=str(self.output),
            required_country=required_country,
        )

    def test_verified_report_maps_source_and_dns_addresses(self):
        result = home_probe_ingest.ingest_report(self.args())
        self.assertEqual(result["source_geoip_category"], "RU")
        self.assertEqual(result["source_matched_ru_prefix"], "5.143.108.0/22")
        self.assertEqual(result["source_candidate_count"], 0)
        self.assertEqual(result["dns_addresses_in_ru_inventory"], 1)
        self.assertEqual(result["dns_addresses_outside_ru_inventory"], 2)

        with (self.output / "home_probe_observations.tsv").open(encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        ipv4_rows = [row for row in rows if row["FAMILY"] == "IPv4"]
        tested = next(row for row in ipv4_rows if row["DNS_ADDRESS"] == "8.8.8.8")
        alternate = next(row for row in ipv4_rows if row["DNS_ADDRESS"] == "1.1.1.1")
        self.assertEqual(tested["HTTPS_RESULT"], "HTTP_RESPONSE")
        self.assertEqual(tested["HTTP_STATUS"], "403")
        self.assertEqual(alternate["HTTPS_RESULT"], "NOT_TESTED_ALTERNATE_ADDRESS")

    def test_source_ip_outside_ru_inventory_creates_exact_ip_candidate_only(self):
        self.write_report(source_ip="77.88.99.100")
        result = home_probe_ingest.ingest_report(self.args())
        self.assertEqual(result["source_geoip_category"], "OUTSIDE_GEOIP_RU")
        self.assertEqual(result["source_candidate_count"], 1)
        with (self.output / "home_probe_candidates.tsv").open(encoding="utf-8") as stream:
            row = next(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(row["CANDIDATE_TYPE"], "HOME_PROBE_SOURCE_IP")
        self.assertEqual(row["SOURCE_PUBLIC_IP"], "77.88.99.100")
        self.assertEqual(row["MATCHED_RU_PREFIX"], "")
        self.assertIn("NO_AUTOMATIC_CIDR_ADDITION", row["REVIEW_POLICY"])

    def test_kz_source_outside_ru_inventory_does_not_become_a_ru_candidate(self):
        self.write_report(
            source_ip="77.88.99.100",
            country="KZ",
            required_country="KZ",
        )
        result = home_probe_ingest.ingest_report(self.args(required_country="KZ"))
        self.assertEqual(result["source_geoip_category"], "OUTSIDE_GEOIP_RU")
        self.assertEqual(result["source_candidate_count"], 0)
        with (self.output / "home_probe_candidates.tsv").open(encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream, delimiter="\\t"))
        self.assertEqual(rows, [])

    def test_unverified_source_metadata_is_rejected(self):
        source = json.loads((self.report / "home_probe_source.json").read_text(encoding="utf-8"))
        source["verified"] = False
        source["status"] = "SOURCE_METADATA_UNVERIFIED"
        (self.report / "home_probe_source.json").write_text(json.dumps(source), encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "not verified"):
            home_probe_ingest.ingest_report(self.args())

    def test_source_country_mismatch_is_rejected(self):
        self.write_report(source_ip="77.88.99.100", country="KZ")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "does not match"):
            home_probe_ingest.ingest_report(self.args())

    def test_provider_observations_must_agree_with_source_ip(self):
        source = json.loads((self.report / "home_probe_source.json").read_text(encoding="utf-8"))
        source["observations"][1]["ip"] = "1.1.1.1"
        (self.report / "home_probe_source.json").write_text(json.dumps(source), encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "do not agree"):
            home_probe_ingest.ingest_report(self.args())

    def test_proxy_environment_in_report_is_rejected(self):
        summary = json.loads((self.report / "home_probe_summary.json").read_text(encoding="utf-8"))
        summary["proxy_environment_variables"] = ["HTTPS_PROXY"]
        (self.report / "home_probe_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "proxy"):
            home_probe_ingest.ingest_report(self.args())
    
    def test_missing_direct_network_attestation_is_rejected(self):
        summary = json.loads((self.report / "home_probe_summary.json").read_text(encoding="utf-8"))
        summary["proxy_environment_clear"] = False
        (self.report / "home_probe_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "proxy"):
            home_probe_ingest.ingest_report(self.args())

    def test_unsupported_report_schema_is_rejected(self):
        summary = json.loads((self.report / "home_probe_summary.json").read_text(encoding="utf-8"))
        summary["schema_version"] = 2
        (self.report / "home_probe_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "schema version"):
            home_probe_ingest.ingest_report(self.args())

    def test_unknown_target_is_rejected(self):
        row = json.loads((self.report / "home_probe_measurements.jsonl").read_text(encoding="utf-8"))
        row["target_id"] = "unknown"
        (self.report / "home_probe_measurements.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "unknown target"):
            home_probe_ingest.ingest_report(self.args())

    def test_private_dns_answer_is_rejected(self):
        row = json.loads((self.report / "home_probe_measurements.jsonl").read_text(encoding="utf-8"))
        row["dns_ipv4_addresses"] = ["10.0.0.5"]
        row["https_ipv4_tested_address"] = "10.0.0.5"
        (self.report / "home_probe_measurements.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "non-global"):
            home_probe_ingest.ingest_report(self.args())

    def test_https_tested_address_must_match_the_observed_dns_address(self):
        row = json.loads((self.report / "home_probe_measurements.jsonl").read_text(encoding="utf-8"))
        row["https_ipv4_tested_address"] = "1.1.1.1"
        (self.report / "home_probe_measurements.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "first observed DNS address"):
            home_probe_ingest.ingest_report(self.args())

    def test_dns_answer_must_have_an_https_attempt(self):
        row = json.loads((self.report / "home_probe_measurements.jsonl").read_text(encoding="utf-8"))
        row["https_ipv4_result"] = "NOT_TESTED"
        row["https_ipv4_tested_address"] = ""
        row["https_ipv4_status"] = None
        (self.report / "home_probe_measurements.jsonl").write_text(json.dumps(row) + "\\n", encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "must have a corresponding HTTPS attempt"):
            home_probe_ingest.ingest_report(self.args())

    def test_dns_no_answer_cannot_claim_an_https_response(self):
        row = json.loads((self.report / "home_probe_measurements.jsonl").read_text(encoding="utf-8"))
        row["dns_ipv4_status"] = "DNS_NO_ANSWER"
        row["dns_ipv4_addresses"] = []
        row["https_ipv4_result"] = "HTTP_RESPONSE"
        row["https_ipv4_tested_address"] = "8.8.8.8"
        (self.report / "home_probe_measurements.jsonl").write_text(json.dumps(row) + "\\n", encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "HTTPS must be NOT_TESTED"):
            home_probe_ingest.ingest_report(self.args())

    def test_source_asn_candidates_must_match_metadata_observations(self):
        source = json.loads((self.report / "home_probe_source.json").read_text(encoding="utf-8"))
        source["asn_candidates"] = [13335]
        (self.report / "home_probe_source.json").write_text(json.dumps(source), encoding="utf-8")
        summary = json.loads((self.report / "home_probe_summary.json").read_text(encoding="utf-8"))
        summary["source_asn_candidates"] = [13335]
        (self.report / "home_probe_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "do not match provider observations"):
            home_probe_ingest.ingest_report(self.args())

    def test_summary_target_role_counts_must_match_measurements(self):
        summary = json.loads((self.report / "home_probe_summary.json").read_text(encoding="utf-8"))
        summary["service_targets"] = 0
        (self.report / "home_probe_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "service target count"):
            home_probe_ingest.ingest_report(self.args())

    def test_summary_source_metadata_must_match_source_report(self):
        summary = json.loads((self.report / "home_probe_summary.json").read_text(encoding="utf-8"))
        summary["source_attribution_status"] = "SOURCE_METADATA_UNVERIFIED"
        (self.report / "home_probe_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "source-attribution status"):
            home_probe_ingest.ingest_report(self.args())

    def test_existing_output_directory_is_never_overwritten(self):
        self.output.mkdir()
        old_file = self.output / "previous.txt"
        old_file.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(home_probe_ingest.ImportError, "not empty"):
            home_probe_ingest.ingest_report(self.args())
        self.assertEqual(old_file.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
