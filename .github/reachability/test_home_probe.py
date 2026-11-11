import argparse
import ipaddress
import json
import pathlib
import socket
import tempfile
import unittest
from unittest.mock import patch

import home_probe


TARGET = {
    "id": "ru-example",
    "domain": "example.ru",
    "role": "service",
    "country_scope": ["RU"],
    "port": 443,
    "path": "/",
}


class SourceMetadataTests(unittest.TestCase):
    def test_source_metadata_requires_two_sources_to_agree(self):
        responses = [
            {
                "ip": "8.8.8.8",
                "country_code": "RU",
                "connection": {"asn": "AS12345", "org": "Example ISP"},
            },
            {
                "ip": "8.8.8.8",
                "country_code": "RU",
                "asn": "AS12345",
                "org": "Example ISP",
            },
        ]
        with patch.object(home_probe, "fetch_json", side_effect=responses):
            result = home_probe.source_metadata(5)
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], "TWO_SOURCE_CONSENSUS")
        self.assertEqual(result["public_ip"], "8.8.8.8")
        self.assertEqual(result["country"], "RU")
        self.assertEqual(result["asn_candidates"], [12345])

    def test_source_metadata_disagreement_is_not_verified(self):
        responses = [
            {"ip": "8.8.8.8", "country_code": "RU", "connection": {}},
            {"ip": "1.1.1.1", "country_code": "RU", "asn": "AS13335"},
        ]
        with patch.object(home_probe, "fetch_json", side_effect=responses):
            result = home_probe.source_metadata(5)
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "SOURCE_METADATA_DISAGREEMENT")
        self.assertEqual(result["public_ip"], "")

    def test_single_metadata_service_is_recorded_but_not_verified(self):
        with patch.object(home_probe, "fetch_json", side_effect=[
            {"ip": "8.8.8.8", "country_code": "RU", "connection": {}},
            home_probe.ProbeError("second service unavailable"),
        ]):
            result = home_probe.source_metadata(5)
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "SOURCE_METADATA_UNVERIFIED")
        self.assertEqual(len(result["observations"]), 1)


class HomeDNSResolutionTests(unittest.TestCase):
    def test_resolver_splits_global_ipv4_and_ipv6_answers(self):
        infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:4860:4860::8888", 443, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::1", 443, 0, 0)),
        ]
        before = socket.getdefaulttimeout()
        with patch.object(home_probe.socket, "getaddrinfo", return_value=infos) as resolver:
            result = home_probe.resolve_families("example.ru", 443, 7)
        resolver.assert_called_once_with("example.ru", 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        self.assertEqual(result["ipv4_status"], "DNS_ANSWER")
        self.assertEqual(result["ipv4_addresses"], ["8.8.8.8"])
        self.assertEqual(result["ipv6_status"], "DNS_ANSWER")
        self.assertEqual(result["ipv6_addresses"], ["2001:4860:4860::8888"])
        self.assertEqual(socket.getdefaulttimeout(), before)

    def test_resolver_failure_is_not_misclassified_as_no_answer(self):
        with patch.object(home_probe.socket, "getaddrinfo", side_effect=socket.gaierror(-3, "temporary failure")):
            result = home_probe.resolve_families("example.ru", 443, 5)
        self.assertEqual(result["ipv4_status"], "DNS_ERROR")
        self.assertEqual(result["ipv6_status"], "DNS_ERROR")
        self.assertIn("temporary failure", result["ipv4_error"])

    def test_successful_ipv4_only_lookup_marks_aaaa_as_no_answer(self):
        infos = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        with patch.object(home_probe.socket, "getaddrinfo", return_value=infos):
            result = home_probe.resolve_families("example.ru", 443, 5)
        self.assertEqual(result["ipv4_status"], "DNS_ANSWER")
        self.assertEqual(result["ipv6_status"], "DNS_NO_ANSWER")


class HomeHTTPSProbeTests(unittest.TestCase):
    def test_pinned_https_preserves_hostname_sni_and_reports_http_response(self):
        class FakeResponse:
            status = 403
            def read(self, limit):
                return b""

        class FakeConnection:
            def __init__(self, hostname, address, port, timeout):
                self.args = (hostname, address, port, timeout)
                self.request_args = None
            def request(self, method, path, headers):
                self.request_args = (method, path, headers)
            def getresponse(self):
                return FakeResponse()
            def close(self):
                pass

        connections = []
        def factory(hostname, address, port, timeout):
            item = FakeConnection(hostname, address, port, timeout)
            connections.append(item)
            return item

        with patch.object(home_probe, "PinnedHTTPSConnection", side_effect=factory):
            result = home_probe.https_head_pinned("example.ru", "8.8.8.8", 443, "/", 5)
        self.assertEqual(result, ("HTTP_RESPONSE", 403, ""))
        self.assertEqual(connections[0].args, ("example.ru", "8.8.8.8", 443, 5))
        self.assertEqual(connections[0].request_args[0:2], ("HEAD", "/"))

    def test_measure_target_uses_at_most_one_address_per_family(self):
        dns = {
            "ipv4_status": "DNS_ANSWER",
            "ipv4_addresses": ["8.8.8.8", "8.8.4.4"],
            "ipv4_error": "",
            "ipv6_status": "DNS_ANSWER",
            "ipv6_addresses": ["2001:4860:4860::8888", "2001:4860:4860::8844"],
            "ipv6_error": "",
        }
        with patch.object(home_probe, "resolve_families", return_value=dns):
            with patch.object(home_probe, "https_head_pinned", side_effect=[
                ("HTTP_RESPONSE", 200, ""),
                ("INCONCLUSIVE", None, "no route"),
            ]) as https:
                row = home_probe.measure_target(TARGET, 5)
        self.assertEqual(https.call_count, 2)
        self.assertEqual(row["https_ipv4_status"], 200)
        self.assertEqual(row["https_ipv6_result"], "INCONCLUSIVE")
        self.assertEqual(row["dns_ipv4_addresses"], ["8.8.8.8", "8.8.4.4"])


class HomeProbeSafetyTests(unittest.TestCase):
    def test_consent_is_required_before_any_target_measurement(self):
        args = argparse.Namespace(
            consent=False, allow_proxy=False, targets="targets.json",
            output_dir="out", required_country="RU", max_targets=None, timeout=5,
        )
        with patch.object(home_probe, "measure_target") as measure:
            with self.assertRaisesRegex(home_probe.ProbeError, "consent"):
                home_probe.run_probe(args)
        measure.assert_not_called()

    def test_proxy_environment_is_rejected_by_default(self):
        args = argparse.Namespace(
            consent=True, allow_proxy=False, targets="targets.json",
            output_dir="out", required_country="RU", max_targets=None, timeout=5,
        )
        with patch.object(home_probe, "proxy_environment", return_value=["HTTPS_PROXY"]):
            with self.assertRaisesRegex(home_probe.ProbeError, "proxy environment"):
                home_probe.run_probe(args)

    def test_reports_are_saved_locally_without_upload(self):
        args = argparse.Namespace(
            consent=True, allow_proxy=False, targets="targets.json",
            output_dir="out", required_country="RU", max_targets=1, timeout=5,
        )
        with tempfile.TemporaryDirectory() as directory:
            args.targets = str(pathlib.Path(directory) / "targets.json")
            args.output_dir = str(pathlib.Path(directory) / "out")
            pathlib.Path(args.targets).write_text(json.dumps({
                "schema_version": 1,
                "countries": ["RU", "KZ", "BY"],
                "targets": [TARGET],
            }), encoding="utf-8")
            with patch.object(home_probe, "source_metadata", return_value={
                "observations": [], "errors": ["metadata unavailable"],
                "verified": False, "status": "SOURCE_METADATA_UNVERIFIED",
                "public_ip": "", "country": "", "asn_candidates": [],
                "organizations": [],
            }):
                with patch.object(home_probe, "measure_target", return_value={
                    "target_id": "ru-example", "https_ipv4_result": "HTTP_RESPONSE",
                    "https_ipv6_result": "NOT_TESTED",
                    "dns_ipv4_status": "DNS_ANSWER", "dns_ipv6_status": "DNS_NO_ANSWER",
                }):
                    with patch.object(home_probe, "fetch_json", side_effect=AssertionError("unexpected direct network")):
                        self.assertEqual(home_probe.run_probe(args), 0)
            output = pathlib.Path(args.output_dir)
            summary = json.loads((output / "home_probe_summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["source_ip_verified_by_two_services"])
            self.assertFalse(summary["automatic_upload"])
            self.assertTrue((output / "home_probe_source.json").is_file())
            self.assertTrue((output / "home_probe_measurements.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
