import datetime as dt
import ipaddress
import json
import pathlib
import tempfile
import unittest

import runner


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
