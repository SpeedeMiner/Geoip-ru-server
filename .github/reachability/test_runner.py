import datetime as dt
import ipaddress
import json
import pathlib
import tempfile
import unittest

import runner


class GlobalpingProbeSchemaTests(unittest.TestCase):
    def test_measurement_probe_flattened_location_is_parsed(self):
        probe = {
            "asn": 25513,
            "city": "Moscow",
            "country": "RU",
            "network": "Moscow city telephone network",
            "tags": ["eyeball-network"],
        }
        metadata = runner.globalping_probe_metadata(probe)
        self.assertEqual(metadata["country"], "RU")
        self.assertEqual(int(metadata["asn"]), 25513)
        self.assertEqual(metadata["city"], "Moscow")
        self.assertIn("eyeball-network", metadata["tags"])

    def test_probe_list_nested_location_is_also_parsed(self):
        probe = {
            "location": {
                "asn": 12389, "country": "RU",
                "city": "Kostroma", "network": "Rostelecom",
            },
            "tags": ["eyeball-network"],
        }
        metadata = runner.globalping_probe_metadata(probe)
        self.assertEqual(metadata["country"], "RU")
        self.assertEqual(int(metadata["asn"]), 12389)
        self.assertEqual(metadata["network"], "Rostelecom")


class ReachabilityInventoryTests(unittest.TestCase):
    def test_ru_endpoint_is_mapped_to_exact_prefix(self):
        networks = {
            "RU": [ipaddress.ip_network("198.51.100.0/24")],
            "PRIVATE": [ipaddress.ip_network("192.0.2.0/24")],
        }
        self.assertEqual(
            runner.map_address("198.51.100.42", networks),
            ("RU", "198.51.100.0/24"),
        )

    def test_private_wins_even_if_input_sets_overlap(self):
        networks = {
            "RU": [ipaddress.ip_network("198.51.100.0/24")],
            "PRIVATE": [ipaddress.ip_network("198.51.100.0/25")],
        }
        self.assertEqual(
            runner.map_address("198.51.100.42", networks),
            ("PRIVATE", "198.51.100.0/25"),
        )

    def test_foreign_service_ip_is_not_assigned_to_ru(self):
        networks = {
            "RU": [ipaddress.ip_network("198.51.100.0/24")],
            "PRIVATE": [ipaddress.ip_network("192.0.2.0/24")],
        }
        self.assertEqual(
            runner.map_address("203.0.113.10", networks),
            ("OUTSIDE_GEOIP_RU", ""),
        )

    def test_invalid_or_missing_endpoint_ip_is_not_misclassified(self):
        networks = {"RU": [], "PRIVATE": []}
        self.assertEqual(runner.map_address(None, networks)[0], "NO_RESOLVED_ADDRESS")
        self.assertEqual(runner.map_address("not-an-ip", networks)[0], "INVALID_ADDRESS")

    def test_inventory_rejects_ru_private_overlap(self):
        contents = (
            "CATEGORY\tPREFIX\tFAMILY\tADDRESS_COUNT\n"
            "RU\t198.51.100.0/24\tIPv4\t256\n"
            "PRIVATE\t198.51.100.0/25\tIPv4\t128\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "inventory.tsv"
            path.write_text(contents, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "RU/PRIVATE overlap"):
                runner.read_inventory(path)


class ReachabilityClassificationTests(unittest.TestCase):
    def test_globalping_no_ipv6_probe_is_not_a_block_verdict(self):
        error = runner.APIError(
            "HTTP 422: {'type': 'no_probes_found', 'message': 'No matching IPv6 probes available.'}",
            422,
        )
        self.assertEqual(
            runner.classify_globalping_api_error(error, "HTTPS", 6),
            "NO_IPV6_PROBE",
        )
        self.assertEqual(
            runner.classify_globalping_api_error(error, "HTTPS", 4),
            "API_ERROR",
        )
        self.assertEqual(
            runner.classify_globalping_api_error(error, "DNS", 6),
            "API_ERROR",
        )

    def test_http_403_is_transport_accessible_not_blocked(self):
        result = runner.classify_globalping_result(
            "RU", 12345, "RU", 12345, {"eyeball-network"},
            "HTTPS", "finished", http_status=403,
        )
        self.assertEqual(result, "ACCESSIBLE")

    def test_timeout_is_inconclusive_not_blocked(self):
        result = runner.classify_globalping_result(
            "RU", 12345, "RU", 12345, {"eyeball-network"},
            "HTTPS", "failed", http_status=None,
        )
        self.assertEqual(result, "INCONCLUSIVE")

    def test_wrong_probe_asn_is_rejected(self):
        result = runner.classify_globalping_result(
            "RU", 12345, "RU", 54321, {"eyeball-network"},
            "HTTPS", "finished", http_status=200,
        )
        self.assertEqual(result, "WRONG_PROBE_SELECTION")

    def test_datacenter_probe_is_rejected(self):
        result = runner.classify_globalping_result(
            "RU", 12345, "RU", 12345, {"datacenter-network"},
            "HTTPS", "finished", http_status=200,
        )
        self.assertEqual(result, "WRONG_PROBE_SELECTION")

    def test_dns_answer_is_not_block_classification(self):
        result = runner.classify_globalping_result(
            "KZ", 9198, "KZ", 9198, {"eyeball-network"},
            "DNS", "finished", answers=[{"type": "A", "value": "198.51.100.5"}],
        )
        self.assertEqual(result, "DNS_ANSWER")

    def test_dns_nxdomain_is_a_dns_observation_not_block_proof(self):
        result = runner.classify_globalping_result(
            "BY", 6697, "BY", 6697, {"eyeball-network"},
            "DNS", "finished", dns_status_code=3,
        )
        self.assertEqual(result, "DNS_NXDOMAIN")


    def test_atlas_probe_verifies_nested_status_country_and_asn(self):
        probe = {
            "id": 123,
            "country_code": "KZ",
            "asn_v4": 9198,
            "asn_v6": 9198,
            "status": {"id": 1, "name": "Connected"},
        }
        self.assertTrue(runner.atlas_probe_matches(probe, "KZ", 9198, 4))
        self.assertTrue(runner.atlas_probe_matches(probe, "KZ", 9198, 6))
        self.assertFalse(runner.atlas_probe_matches(probe, "RU", 9198, 4))
        self.assertFalse(runner.atlas_probe_matches(probe, "KZ", 12389, 4))

    def test_atlas_probe_rejects_disconnected_or_missing_status(self):
        disconnected = {
            "country_code": "RU", "asn_v4": 12345,
            "status": {"id": 2, "name": "Disconnected"},
        }
        missing = {"country_code": "RU", "asn_v4": 12345}
        self.assertFalse(runner.atlas_probe_matches(disconnected, "RU", 12345, 4))
        self.assertFalse(runner.atlas_probe_matches(missing, "RU", 12345, 4))


class TaskAndReportTests(unittest.TestCase):
    def test_tasks_include_dns_and_https_for_each_address_family(self):
        targets = [{
            "id": "demo", "domain": "example.net", "role": "control",
            "country_scope": ["RU"], "port": 443, "path": "/",
        }]
        providers = {
            ("RU", 12345): {
                "country": "RU", "asn": 12345, "network": "Test ISP",
                "city": "Moscow", "tags": ["eyeball-network"],
                "probe_class": "eyeball_network_unverified",
            }
        }
        tasks = runner.build_tasks(targets, providers)
        self.assertEqual(len(tasks), 4)
        self.assertEqual({(task["kind"], task["ip_family"]) for task in tasks}, {
            ("DNS", 4), ("DNS", 6), ("HTTPS", 4), ("HTTPS", 6),
        })

    def test_rotation_is_deterministic_and_selects_every_task_over_windows(self):
        tasks = [{"n": n} for n in range(10)]
        first, _ = runner.rotate_tasks(tasks, 4, dt.date(2026, 11, 10))
        second, _ = runner.rotate_tasks(tasks, 4, dt.date(2026, 11, 11))
        self.assertEqual(len(first), 4)
        self.assertEqual(len(second), 4)
        self.assertTrue({row["n"] for row in first}.isdisjoint({row["n"] for row in second}))

    def test_fair_schedule_covers_all_three_countries_before_second_bundles(self):
        targets = [
            {
                "id": target_id, "domain": f"{target_id}.example", "role": "service",
                "country_scope": ["RU", "KZ", "BY"], "port": 443, "path": "/",
            }
            for target_id in ("target-a", "target-b", "target-c")
        ]
        providers = {}
        for country, asns in {
            "RU": [12389, 25513, 29226, 31357],
            "KZ": [9198, 21299],
            "BY": [6697, 25106],
        }.items():
            for asn in asns:
                providers[(country, asn)] = {
                    "country": country, "asn": asn, "network": f"ISP AS{asn}",
                    "city": "test", "tags": ["eyeball-network"],
                    "probe_class": "eyeball_network_unverified",
                }
        tasks = runner.build_tasks(targets, providers)
        selected, meta = runner.select_fair_provider_tasks(
            tasks, 4 * len(providers), dt.date(2026, 11, 10)
        )
        self.assertEqual(meta["providers_covered"], len(providers))
        self.assertEqual(meta["providers_uncovered"], 0)
        self.assertEqual(set(meta["countries_selected"]), {"RU", "KZ", "BY"})
        self.assertEqual(len(selected), 4 * len(providers))
        counts = {}
        for row in selected:
            key = (row["country"], row["asn"])
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(set(counts), set(providers))
        self.assertTrue(all(value == 4 for value in counts.values()))
        signatures = {}
        for row in selected:
            signatures.setdefault((row["country"], row["asn"]), set()).add(
                (row["kind"], row["ip_family"])
            )
        expected = {("DNS", 4), ("DNS", 6), ("HTTPS", 4), ("HTTPS", 6)}
        self.assertTrue(all(value == expected for value in signatures.values()))

    def test_fair_schedule_default_budget_does_not_starve_providers(self):
        targets = [
            {
                "id": target_id, "domain": f"{target_id}.example", "role": "service",
                "country_scope": ["RU", "KZ", "BY"], "port": 443, "path": "/",
            }
            for target_id in ("target-a", "target-b")
        ]
        providers = {}
        for country, first_asn, count in (("RU", 10000, 27), ("KZ", 20000, 7), ("BY", 30000, 3)):
            for offset in range(count):
                asn = first_asn + offset
                providers[(country, asn)] = {
                    "country": country, "asn": asn, "network": f"ISP AS{asn}",
                    "city": "test", "tags": ["eyeball-network"],
                    "probe_class": "eyeball_network_unverified",
                }
        tasks = runner.build_tasks(targets, providers)
        selected, meta = runner.select_fair_provider_tasks(
            tasks, 180, dt.date(2026, 11, 10)
        )
        self.assertEqual(len(providers), 37)
        self.assertEqual(len(selected), 180)
        self.assertEqual(meta["providers_covered"], 37)
        self.assertEqual(meta["providers_uncovered"], 0)
        self.assertEqual(set(meta["countries_selected"]), {"RU", "KZ", "BY"})
        per_provider = {}
        for row in selected:
            key = (row["country"], row["asn"])
            per_provider[key] = per_provider.get(key, 0) + 1
        self.assertTrue(all(count >= 4 for count in per_provider.values()))
        self.assertEqual(sum(count // 4 for count in per_provider.values()), 45)

    def test_fair_schedule_reports_uncovered_providers_when_budget_is_too_small(self):
        targets = [{
            "id": "only", "domain": "only.example", "role": "service",
            "country_scope": ["RU", "KZ", "BY"], "port": 443, "path": "/",
        }]
        providers = {
            (country, asn): {
                "country": country, "asn": asn, "network": f"ISP AS{asn}",
                "city": "test", "tags": ["eyeball-network"],
                "probe_class": "eyeball_network_unverified",
            }
            for country, asn in (("RU", 12389), ("KZ", 9198), ("BY", 6697))
        }
        tasks = runner.build_tasks(targets, providers)
        selected, meta = runner.select_fair_provider_tasks(
            tasks, 7, dt.date(2026, 11, 10)
        )
        self.assertEqual(len(selected), 4)
        self.assertEqual(meta["providers_covered"], 1)
        self.assertEqual(meta["providers_uncovered"], 2)
        self.assertEqual(meta["partial_target_bundles"], 0)
        self.assertEqual(meta["budget_unused_for_bundle_alignment"], 3)

    def test_prefix_report_distinguishes_dns_from_inconclusive_https(self):
        inventory = [
            {"CATEGORY": "RU", "PREFIX": "198.51.100.0/24", "FAMILY": "IPv4", "ADDRESS_COUNT": "256"},
            {"CATEGORY": "PRIVATE", "PREFIX": "192.0.2.0/24", "FAMILY": "IPv4", "ADDRESS_COUNT": "256"},
        ]
        measurements = [
            {
                "result": "DNS_ANSWER", "matched_ru_prefix": "198.51.100.0/24",
                "target_id": "service", "target_ip": "198.51.100.10",
            },
            {
                "result": "INCONCLUSIVE", "matched_ru_prefix": "198.51.100.0/24",
                "target_id": "service", "target_ip": "198.51.100.10",
            },
        ]
        report = runner.build_prefix_report(inventory, measurements)
        self.assertEqual(report[0]["STATUS"], "DNS_RESOLVED_HTTP_INCONCLUSIVE")

    def test_provider_prefix_report_preserves_country_asn_and_observed_ips(self):
        measurements = [
            {
                "probe_country": "KZ", "probe_asn": 9198, "probe_network": "Kazakhtelecom",
                "matched_ru_prefix": "198.51.100.0/24", "matched_ru_prefixes": "198.51.100.0/24",
                "target_id": "demo", "target_domain": "demo.example",
                "resolved_addresses": "198.51.100.10", "target_ip": "198.51.100.10",
                "result": "ACCESSIBLE", "http_status": 200,
            },
            {
                "probe_country": "KZ", "probe_asn": 9198, "probe_network": "Kazakhtelecom",
                "matched_ru_prefix": "198.51.100.0/24", "matched_ru_prefixes": "198.51.100.0/24",
                "target_id": "demo", "target_domain": "demo.example",
                "resolved_addresses": "198.51.100.10", "target_ip": "198.51.100.10",
                "result": "DNS_ANSWER", "measurement_kind": "DNS",
            },
        ]
        report = runner.build_provider_prefix_report(measurements)
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["COUNTRY"], "KZ")
        self.assertEqual(report[0]["ASN"], 9198)
        self.assertEqual(report[0]["PREFIX"], "198.51.100.0/24")
        self.assertEqual(report[0]["ACCESSIBLE_HTTPS"], 1)
        self.assertEqual(report[0]["DNS_ANSWERS"], 1)
        self.assertEqual(report[0]["OBSERVED_IPS"], "198.51.100.10")

    def test_provider_ip_report_maps_exact_ru_ip_to_provider(self):
        networks = {
            "RU": [ipaddress.ip_network("198.51.100.0/24")],
            "PRIVATE": [ipaddress.ip_network("192.0.2.0/24")],
        }
        measurements = [
            {
                "probe_country": "BY", "probe_asn": 42772, "probe_network": "A1",
                "resolved_addresses": "198.51.100.12", "target_ip": "198.51.100.12",
                "target_id": "demo", "target_domain": "demo.example",
                "measurement_kind": "HTTPS", "http_status": 302, "result": "ACCESSIBLE",
            },
            {
                "probe_country": "BY", "probe_asn": 42772, "probe_network": "A1",
                "resolved_addresses": "198.51.100.12", "target_ip": "198.51.100.12",
                "target_id": "demo", "target_domain": "demo.example",
                "measurement_kind": "DNS", "result": "DNS_ANSWER",
            },
        ]
        report = runner.build_provider_ip_report(measurements, networks)
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["COUNTRY"], "BY")
        self.assertEqual(report[0]["ASN"], 42772)
        self.assertEqual(report[0]["IP_ADDRESS"], "198.51.100.12")
        self.assertEqual(report[0]["PREFIX"], "198.51.100.0/24")
        self.assertEqual(report[0]["STATUS"], "HTTPS_ACCESSIBLE_OBSERVED")
        self.assertEqual(report[0]["HTTPS_ACCESSIBLE_COUNT"], 1)
        self.assertEqual(report[0]["DNS_ANSWER_COUNT"], 1)

    def test_prefix_report_contains_ru_only_and_explicit_no_endpoint_state(self):
        inventory = [
            {"CATEGORY": "RU", "PREFIX": "198.51.100.0/24", "FAMILY": "IPv4", "ADDRESS_COUNT": "256"},
            {"CATEGORY": "PRIVATE", "PREFIX": "192.0.2.0/24", "FAMILY": "IPv4", "ADDRESS_COUNT": "256"},
        ]
        report = runner.build_prefix_report(inventory, [])
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["STATUS"], "NO_MATCHED_ENDPOINT")
        self.assertEqual(report[0]["POLICY"], "REVIEW_ONLY_NO_GEOIP_MUTATION")


if __name__ == "__main__":
    unittest.main()
