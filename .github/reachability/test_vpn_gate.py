import base64
import csv
import io
import json
import os
import signal
import urllib.error
import urllib.request
import pathlib
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import vpn_gate


def _vpnobratto_worker_test_success(url, timeout, max_bytes):
    return f"{url}|{timeout}|{max_bytes}".encode("ascii")


def _vpnobratto_worker_test_hang(pid_path, timeout, max_bytes):
    pathlib.Path(pid_path).write_text(str(os.getpid()), encoding="ascii")
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(0.05)


def _vpnobratto_worker_test_crash(_url, *, timeout, max_bytes):
    # The production worker invokes fetchers with named timeout/max_bytes args.
    _ = (timeout, max_bytes)
    os._exit(17)


SAMPLE_CONFIG = """client
dev tun
proto tcp
remote old-volunteer-host.opengw.net 443
remote-cert-tls server
cipher AES-128-CBC
auth SHA1
key-direction 1
<ca>
-----BEGIN CERTIFICATE-----
VEVTVENB
-----END CERTIFICATE-----
</ca>
<tls-auth>
#
# 2048 bit OpenVPN static key
#
-----BEGIN OpenVPN Static key V1-----
VEVUS0VZ
-----END OpenVPN Static key V1-----
</tls-auth>
up /tmp/untrusted-up.sh
down /tmp/untrusted-down.sh
plugin /tmp/untrusted-plugin.so
script-security 2
"""


def sample_csv(rows):
    header = [
        "HostName", "IP", "Score", "Ping", "Speed", "CountryLong",
        "CountryShort", "NumVpnSessions", "Uptime", "TotalUsers",
        "TotalTraffic", "LogType", "Operator", "Message",
        "OpenVPN_ConfigData_Base64",
    ]
    output = io.StringIO()
    output.write("*vpn_servers\n")
    output.write("#" + ",".join(header) + "\n")
    writer = csv.writer(output, lineterminator="\n")
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def row(host, ip, country="RU", config=SAMPLE_CONFIG):
    return [
        host, ip, "100000", "20", "100000000", "Russian Federation",
        country, "5", "2 days", "1000", "100", "0", "operator",
        "sample", base64.b64encode(config.encode()).decode(),
    ]


class VPNGateCSVTests(unittest.TestCase):
    def test_only_public_ru_openvpn_servers_are_selected(self):
        text = sample_csv([
            row("ru-node.opengw.net", "8.8.8.8"),
            row("foreign-node.opengw.net", "1.1.1.1", country="US"),
            row("private-node.opengw.net", "10.0.0.1"),
        ])
        servers = vpn_gate.parse_vpngate_csv(text)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]["hostname"], "ru-node.opengw.net")
        self.assertEqual(servers[0]["server_ip"], "8.8.8.8")
        self.assertEqual(servers[0]["country_short"], "RU")
        self.assertEqual(servers[0]["profile"]["port"], 443)
        self.assertEqual(servers[0]["profile"]["proto"], "tcp-client")

    def test_csv_header_must_be_present_and_complete(self):
        with self.assertRaisesRegex(ValueError, "header"):
            vpn_gate.parse_vpngate_csv("not a VPN Gate CSV")
        incomplete = "*vpn_servers\n#HostName,IP\nnode,8.8.8.8\n"
        with self.assertRaisesRegex(ValueError, "missing columns"):
            vpn_gate.parse_vpngate_csv(incomplete)

    def test_malformed_or_unsupported_openvpn_profiles_are_skipped(self):
        unsupported = SAMPLE_CONFIG.replace("proto tcp", "proto sctp")
        text = sample_csv([
            row("bad-proto.opengw.net", "8.8.8.8", config=unsupported),
            row("missing-ca.opengw.net", "9.9.9.9", config=SAMPLE_CONFIG.replace(
                "<ca>\n-----BEGIN CERTIFICATE-----\nVEVTVENB\n-----END CERTIFICATE-----\n</ca>\n", ""
            )),
        ])
        self.assertEqual(vpn_gate.parse_vpngate_csv(text), [])


class VPNExitVerificationTests(unittest.TestCase):
    def test_exit_ip_requires_two_independent_matching_sources(self):
        responses = [
            {
                "ip": "8.8.8.8", "country_code": "RU",
                "connection": {"asn": "AS12345", "org": "Example ISP"},
            },
            {
                "ip": "8.8.8.8", "country_code": "RU",
                "asn": "AS12345", "org": "Example ISP",
            },
        ]
        with patch.object(vpn_gate, "fetch_json", side_effect=responses):
            info = vpn_gate.ip_metadata()
        self.assertEqual(info["ip"], "8.8.8.8")
        self.assertEqual(info["country"], "RU")
        self.assertEqual(info["asn"], 12345)
        self.assertEqual(info["verified_by_sources"], 2)
        self.assertIn("|", info["source"])

    def test_exit_ip_rejects_country_or_address_disagreement(self):
        responses = [
            {"ip": "8.8.8.8", "country_code": "RU", "connection": {}},
            {"ip": "1.1.1.1", "country_code": "RU", "connection": {}},
        ]
        with patch.object(vpn_gate, "fetch_json", side_effect=responses):
            with self.assertRaisesRegex(vpn_gate.ProbeError, "disagree"):
                vpn_gate.ip_metadata()

    def test_exit_ip_requires_two_working_metadata_services(self):
        first = {"ip": "8.8.8.8", "country_code": "RU", "connection": {}}
        with patch.object(vpn_gate, "fetch_json", side_effect=[
            first, vpn_gate.ProbeError("offline"), vpn_gate.ProbeError("offline")
        ]):
            with self.assertRaisesRegex(vpn_gate.ProbeError, "two independent"):
                vpn_gate.ip_metadata()

    def test_server_selection_prefers_distinct_hostnames_without_network_lookup(self):
        servers = [
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 100},
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 95},
            {"hostname": "b", "server_ip": "8.8.8.2", "score": 90},
            {"hostname": "c", "server_ip": "8.8.8.3", "score": 80},
            {"hostname": "d", "server_ip": "8.8.8.4", "score": 70},
        ]
        with patch.object(vpn_gate, "network_info") as lookup:
            selected, metadata = vpn_gate.select_server_host_diverse_candidates(servers, 3)

        self.assertEqual([server["hostname"] for server in selected], ["a", "b", "c"])
        self.assertEqual(metadata["selected_server_hosts"], ["a", "b", "c"])
        self.assertEqual(metadata["selected_distinct_asns"], 0)
        self.assertEqual(metadata["server_asn_lookups"], 0)
        self.assertEqual(metadata["candidate_servers_inspected"], 4)
        lookup.assert_not_called()

    def test_server_selection_uses_second_variant_only_after_distinct_hosts(self):
        servers = [
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 100, "profile_variant": "IP_UDP"},
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 95, "profile_variant": "DDNS_UDP"},
            {"hostname": "b", "server_ip": "8.8.8.2", "score": 90, "profile_variant": "IP_UDP"},
            {"hostname": "c", "server_ip": "8.8.8.3", "score": 80, "profile_variant": "IP_UDP"},
        ]
        selected, metadata = vpn_gate.select_server_host_diverse_candidates(
            servers, max_servers=1, max_attempts=3
        )
        self.assertEqual([server["hostname"] for server in selected], ["a", "b", "c"])
        self.assertEqual(metadata["distinct_candidate_server_hosts"], 3)
        self.assertEqual(metadata["candidate_servers_inspected"], 4)

    def test_one_successful_exit_allows_three_distinct_host_fallback_attempts(self):
        servers = [
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 100},
            {"hostname": "b", "server_ip": "8.8.8.2", "score": 90},
            {"hostname": "c", "server_ip": "8.8.8.3", "score": 80},
            {"hostname": "d", "server_ip": "8.8.8.4", "score": 70},
        ]
        selected, metadata = vpn_gate.select_server_host_diverse_candidates(
            servers, max_servers=1, max_attempts=3
        )
        self.assertEqual([server["hostname"] for server in selected], ["a", "b", "c"])
        self.assertEqual(metadata["selected_distinct_asns"], 0)
        self.assertEqual(metadata["max_connection_attempts"], 3)

    def test_max_attempts_cannot_be_lower_than_successful_exit_target(self):
        with self.assertRaisesRegex(ValueError, "max_attempts"):
            vpn_gate.select_server_host_diverse_candidates([], max_servers=2, max_attempts=1)

    def test_selection_stops_when_distinct_host_attempt_budget_is_met(self):
        servers = [
            {"hostname": f"host-{index}", "server_ip": f"8.8.8.{index}", "score": 100 - index}
            for index in range(1, 11)
        ]
        with patch.object(vpn_gate, "network_info") as lookup:
            selected, metadata = vpn_gate.select_server_host_diverse_candidates(
                servers, max_servers=1, max_attempts=6
            )

        self.assertEqual(len(selected), 6)
        self.assertEqual(metadata["candidate_servers_inspected"], 6)
        self.assertEqual(metadata["distinct_candidate_server_hosts"], 6)
        self.assertEqual(metadata["server_asn_lookups"], 0)
        self.assertEqual(metadata["selected_distinct_asns"], 0)
        lookup.assert_not_called()

    def test_selection_keeps_scanning_when_distinct_host_budget_not_yet_met(self):
        servers = [
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 100},
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 95},
            {"hostname": "b", "server_ip": "8.8.8.2", "score": 90},
            {"hostname": "c", "server_ip": "8.8.8.3", "score": 80},
        ]
        selected, metadata = vpn_gate.select_server_host_diverse_candidates(
            servers, max_servers=1, max_attempts=3
        )

        self.assertEqual(metadata["candidate_servers_inspected"], 4)
        self.assertEqual(metadata["distinct_candidate_server_hosts"], 3)
        self.assertEqual(metadata["selected_distinct_asns"], 0)
        self.assertEqual([server["hostname"] for server in selected], ["a", "b", "c"])

class RIPEstatNetworkInfoTests(unittest.TestCase):
    def test_network_prefix_is_kept_only_when_it_contains_the_query_ip(self):
        with patch.object(vpn_gate, "fetch_json", return_value={
            "data": {"prefix": "8.8.8.0/24", "asns": ["AS15169"]}
        }):
            result = vpn_gate.network_info("8.8.8.8")
        self.assertEqual(result, {"prefix": "8.8.8.0/24", "asn": 15169})

    def test_network_prefix_mismatch_is_discarded_but_asn_is_preserved(self):
        with patch.object(vpn_gate, "fetch_json", return_value={
            "data": {"prefix": "1.1.1.0/24", "asns": ["AS15169"]}
        }):
            result = vpn_gate.network_info("8.8.8.8")
        self.assertEqual(result, {"prefix": "", "asn": 15169})


class VPNGateMeasurementStatusTests(unittest.TestCase):
    def test_target_scan_summary_reports_unverified_and_partial_scans(self):
        not_started = vpn_gate.summarize_target_scans([])
        self.assertEqual(
            not_started["target_scan_status"],
            "NOT_STARTED_NO_VERIFIED_RU_EXIT",
        )
        partial = vpn_gate.summarize_target_scans([{
            "server_hostname": "vpn.example.net",
            "targets_requested": 30,
            "targets_tested": 28,
            "targets_not_tested": ["by-kufar", "by-nbrb"],
            "complete": False,
        }])
        self.assertEqual(partial["target_scan_status"], "PARTIAL")
        self.assertEqual(partial["target_scans_incomplete"], 1)
        self.assertEqual(partial["targets_not_tested_count"], 2)
        self.assertEqual(
            partial["targets_not_tested"],
            [{
                "server_hostname": "vpn.example.net",
                "target_ids": ["by-kufar", "by-nbrb"],
            }],
        )
        complete = vpn_gate.summarize_target_scans([{
            "server_hostname": "vpn.example.net",
            "targets_requested": 30,
            "targets_tested": 30,
            "targets_not_tested": [],
            "complete": True,
        }])
        self.assertEqual(complete["target_scan_status"], "COMPLETE")
        self.assertEqual(complete["targets_not_tested_count"], 0)

    def test_no_verified_ru_exit_is_not_a_successful_measurement(self):
        self.assertNotEqual(vpn_gate.measurement_exit_code(0, 1), 0)
        self.assertEqual(vpn_gate.measurement_exit_code(1, 1), 0)
        self.assertEqual(vpn_gate.measurement_exit_code(2, 1), 0)

    def test_partial_target_scan_is_not_a_successful_measurement(self):
        self.assertNotEqual(
            vpn_gate.measurement_exit_code(1, 1, "PARTIAL"),
            0,
        )
        self.assertNotEqual(
            vpn_gate.measurement_exit_code(1, 1, "NOT_STARTED_NO_VERIFIED_RU_EXIT"),
            0,
        )
        self.assertEqual(
            vpn_gate.measurement_exit_code(1, 1, "COMPLETE"),
            0,
        )


class VPNGateHandshakeFailureTests(unittest.TestCase):
    def test_tls_handshake_failure_stops_wait_early(self):
        class RunningProcess:
            returncode = None
            def poll(self):
                return None

        with tempfile.TemporaryDirectory() as directory:
            log_path = pathlib.Path(directory) / "openvpn.log"
            log_path.write_text(
                "TCP connection established\\nTLS key negotiation failed to occur within 60 seconds\\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(vpn_gate.ProbeError, "TLS key negotiation failed"):
                vpn_gate.wait_for_tunnel(RunningProcess(), 60, log_path)


class UbuntuAptDNSBootstrapTests(unittest.TestCase):
    def test_privileged_workflow_bootstrap_disables_python_bytecode_cache(self):
        workflow = (
            pathlib.Path(__file__).resolve().parents[1]
            / "workflows"
            / "reachability-vpn-gate.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "sudo timeout --signal=TERM --kill-after=2s 45s python3 -B - <<'PY'",
            workflow,
        )
        self.assertIn("    timeout-minutes: 12\n", workflow)
        self.assertIn("        timeout-minutes: 9\n", workflow)
        self.assertIn(
            "bash .github/reachability/vpn_netns_exec.sh -- \\",
            workflow,
        )
        self.assertIn("sudo env \\", workflow)
        self.assertIn("GITHUB_SHA=\"${GITHUB_SHA}\"", workflow)
        self.assertIn("GITHUB_RUN_ID=\"${GITHUB_RUN_ID}\"", workflow)
        self.assertIn("GITHUB_RUN_ATTEMPT=\"${GITHUB_RUN_ATTEMPT}\"", workflow)
        self.assertIn(
            "timeout --verbose --signal=TERM --kill-after=5s 7m \\",
            workflow,
        )

    def test_namespace_wrapper_keeps_host_control_plane_outside_vpn_firewall(self):
        wrapper = (
            pathlib.Path(__file__).resolve().parent / "vpn_netns_exec.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("ip netns add", wrapper)
        self.assertIn('ip netns exec "$NAMESPACE" "$@"', wrapper)
        self.assertIn("iptables -I FORWARD", wrapper)
        self.assertIn("iptables -t nat -I POSTROUTING", wrapper)
        self.assertIn("trap cleanup EXIT", wrapper)
        self.assertIn("trap 'forward_signal TERM 143' TERM", wrapper)
        self.assertIn('wait "$CHILD_PID"', wrapper)
        self.assertIn('sysctl -w "net.ipv4.ip_forward=$IPV4_FORWARD_OLD"', wrapper)
        self.assertNotIn('iptables -P OUTPUT DROP', wrapper)

    def test_sigterm_handler_unwinds_context_managers(self):
        restored = []

        class Guard:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                restored.append(exc_type)
                return False

        try:
            with Guard():
                vpn_gate.handle_termination_signal(signal.SIGTERM, None)
        except SystemExit as exc:
            raised = exc
        else:
            self.fail("SIGTERM handler must terminate through SystemExit")

        self.assertEqual(raised.code, 128 + signal.SIGTERM)
        self.assertEqual(restored, [SystemExit])


    def test_pinned_doh_answers_create_public_ipv4_hosts_overrides(self):
        answers = {
            "azure.archive.ubuntu.com": ["8.8.8.8", "10.0.0.1", "2001:4860:4860::8888"],
            "archive.ubuntu.com": ["1.1.1.1"],
            "security.ubuntu.com": ["9.9.9.9", "127.0.0.1"],
        }
        calls = []

        def resolver(hostname, record_type, timeout):
            calls.append((hostname, record_type, timeout))
            return answers[hostname]

        with tempfile.TemporaryDirectory() as directory:
            hosts_file = pathlib.Path(directory) / "hosts"
            hosts_file.write_text("127.0.0.1 localhost\n", encoding="utf-8")
            resolved = vpn_gate.install_ubuntu_apt_host_overrides(hosts_file, resolver)

            self.assertEqual(resolved, {
                "azure.archive.ubuntu.com": ["8.8.8.8"],
                "archive.ubuntu.com": ["1.1.1.1"],
                "security.ubuntu.com": ["9.9.9.9"],
            })
            contents = hosts_file.read_text(encoding="utf-8")
            self.assertIn("8.8.8.8 azure.archive.ubuntu.com", contents)
            self.assertIn("1.1.1.1 archive.ubuntu.com", contents)
            self.assertIn("9.9.9.9 security.ubuntu.com", contents)
            self.assertEqual(calls, [
                (hostname, "A", 5)
                for hostname in vpn_gate.UBUNTU_APT_MIRROR_HOSTS
            ])

            vpn_gate.install_ubuntu_apt_host_overrides(hosts_file, resolver)
            self.assertEqual(
                hosts_file.read_text(encoding="utf-8").count(vpn_gate.APT_HOSTS_BLOCK_START),
                1,
            )

    def test_doh_failure_does_not_write_a_partial_hosts_override(self):
        with tempfile.TemporaryDirectory() as directory:
            hosts_file = pathlib.Path(directory) / "hosts"
            original = "127.0.0.1 localhost\n"
            hosts_file.write_text(original, encoding="utf-8")

            def resolver(hostname, record_type, timeout):
                if hostname == "security.ubuntu.com":
                    raise vpn_gate.ProbeError("resolver unavailable")
                return ["8.8.8.8"]

            with self.assertRaisesRegex(vpn_gate.ProbeError, "security.ubuntu.com"):
                vpn_gate.install_ubuntu_apt_host_overrides(hosts_file, resolver)
            self.assertEqual(hosts_file.read_text(encoding="utf-8"), original)

    def test_invalid_hosts_file_markers_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            hosts_file = pathlib.Path(directory) / "hosts"
            hosts_file.write_text(
                "127.0.0.1 localhost\n" + vpn_gate.APT_HOSTS_BLOCK_START + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(vpn_gate.ProbeError, "inconsistent"):
                vpn_gate.install_ubuntu_apt_host_overrides(
                    hosts_file,
                    lambda hostname, record_type, timeout: ["8.8.8.8"],
                )


class VPNGateDoHTests(unittest.TestCase):
    def test_doh_query_uses_pinned_resolver_and_filters_requested_type(self):
        class FakeSocket:
            def __init__(self):
                self.timeouts = []
            def settimeout(self, value):
                self.timeouts.append(value)

        class FakeResponse:
            status = 200
            def __init__(self, sock):
                self.fp = type("FakeFP", (), {
                    "raw": type("FakeRaw", (), {"_sock": sock})()
                })()
                self.payload = json.dumps({
                    "Status": 0,
                    "Answer": [
                        {"type": 1, "data": "8.8.8.8"},
                        {"type": 28, "data": "2001:4860:4860::8888"},
                        {"type": 1, "data": "10.0.0.1"},
                    ],
                }).encode()
                self.read = False
            def read1(self, limit):
                if self.read:
                    return b""
                self.read = True
                return self.payload[:limit]

        class FakeConnection:
            def __init__(self, host, address, timeout):
                self.host, self.address, self.timeout = host, address, timeout
                self.request_args = None
                self.sock = FakeSocket()
            def request(self, method, path, headers):
                self.request_args = (method, path, headers)
            def getresponse(self):
                return FakeResponse(self.sock)
            def close(self):
                pass

        made = []
        def factory(host, address, timeout):
            connection = FakeConnection(host, address, timeout)
            made.append(connection)
            return connection

        with patch.object(vpn_gate, "PinnedHTTPSConnection", side_effect=factory):
            result = vpn_gate.doh_query("example.com", "A")
        self.assertEqual(result, ["8.8.8.8"])
        self.assertEqual(made[0].host, "cloudflare-dns.com")
        self.assertEqual(made[0].address, "1.1.1.1")
        self.assertIn("type=A", made[0].request_args[1])
        self.assertGreaterEqual(len(made[0].sock.timeouts), 2)

    def test_doh_query_enforces_one_absolute_deadline_during_slow_drip(self):
        clock = [0.0]
        made = []

        class FakeSocket:
            def __init__(self):
                self.timeouts = []
            def settimeout(self, value):
                self.timeouts.append(value)

        class SlowResponse:
            status = 200
            def __init__(self, sock):
                self.fp = type("FakeFP", (), {
                    "raw": type("FakeRaw", (), {"_sock": sock})()
                })()
                self.reads = 0
            def read1(self, _limit):
                self.reads += 1
                clock[0] += 0.6
                return b"x"

        class FakeConnection:
            def __init__(self, host, address, timeout):
                self.host, self.address, self.timeout = host, address, timeout
                self.sock = FakeSocket()
                self.response = SlowResponse(self.sock)
                made.append(self)
            def request(self, *_args, **_kwargs):
                pass
            def getresponse(self):
                return self.response
            def close(self):
                pass

        with patch.object(vpn_gate.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(vpn_gate, "PinnedHTTPSConnection", side_effect=FakeConnection):
            with self.assertRaisesRegex(vpn_gate.ProbeError, "all pinned DNS-over-HTTPS resolvers failed"):
                vpn_gate.doh_query("example.com", "A", timeout=1)

        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].response.reads, 2)
        self.assertGreaterEqual(len(made[0].sock.timeouts), 3)
        self.assertLess(made[0].sock.timeouts[-1], made[0].sock.timeouts[0])

    def test_doh_query_does_not_retry_after_outer_alarm_timeout(self):
        clock = [0.0]
        made = []

        class FakeSocket:
            def settimeout(self, _value):
                pass

        class AlarmResponse:
            status = 200
            def __init__(self, sock):
                self.fp = type("FakeFP", (), {
                    "raw": type("FakeRaw", (), {"_sock": sock})()
                })()
            def read1(self, _limit):
                clock[0] = 1.1
                raise TimeoutError("wall-clock deadline")

        class FakeConnection:
            def __init__(self, host, address, timeout):
                self.host, self.address, self.timeout = host, address, timeout
                self.sock = FakeSocket()
                self.response = AlarmResponse(self.sock)
                made.append(self)
            def request(self, *_args, **_kwargs):
                pass
            def getresponse(self):
                return self.response
            def close(self):
                pass

        with (
            patch.object(vpn_gate.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(vpn_gate, "PinnedHTTPSConnection", side_effect=FakeConnection),
        ):
            with self.assertRaisesRegex(vpn_gate.ProbeError, "all pinned DNS-over-HTTPS resolvers failed"):
                vpn_gate.doh_query("example.com", "A", timeout=1)

        self.assertEqual(len(made), 1)

    def test_system_dns_failure_falls_back_to_pinned_doh_for_both_families(self):
        with patch.object(vpn_gate.socket, "getaddrinfo", side_effect=socket.gaierror(-3, "temporary failure")):
            with patch.object(vpn_gate, "doh_query", side_effect=[
                ["8.8.8.8"], ["2001:4860:4860::8888"]
            ]) as doh:
                ipv4, ipv6 = vpn_gate.resolve_domain_families("example.com", 5)
        self.assertEqual(ipv4, ("DNS_ANSWER", ["8.8.8.8"], ""))
        self.assertEqual(ipv6, ("DNS_ANSWER", ["2001:4860:4860::8888"], ""))
        self.assertEqual([call.args[1] for call in doh.call_args_list], ["A", "AAAA"])

    def test_metadata_fetch_uses_pinned_https_when_system_dns_fails(self):
        opener = type("Opener", (), {
            "open": lambda self, request, timeout: (_ for _ in ()).throw(
                urllib.error.URLError("temporary DNS failure")
            )
        })()
        with patch.object(vpn_gate.urllib.request, "build_opener", return_value=opener):
            with patch.object(vpn_gate, "fetch_https_pinned", return_value=b'{"ip":"8.8.8.8"}') as pinned:
                payload = vpn_gate.fetch_bytes("https://ipwho.is/", timeout=5)
        self.assertEqual(payload, b'{"ip":"8.8.8.8"}')
        pinned.assert_called_once_with("https://ipwho.is/", 5)


    def test_https_head_uses_pinned_sni_fallback_after_system_dns_failure(self):
        opener = type("Opener", (), {
            "open": lambda self, request, timeout: (_ for _ in ()).throw(
                urllib.error.URLError("temporary DNS failure")
            )
        })()

        class FakeResponse:
            status = 403
            def read(self, limit):
                return b""

        class FakeConnection:
            def __init__(self, host, address, port, timeout):
                self.args = (host, address, port, timeout)
                self.request_args = None
            def request(self, method, path, headers):
                self.request_args = (method, path, headers)
            def getresponse(self):
                return FakeResponse()
            def close(self):
                pass

        connections = []
        def factory(host, address, port, timeout):
            connection = FakeConnection(host, address, port, timeout)
            connections.append(connection)
            return connection

        with patch.object(vpn_gate.urllib.request, "build_opener", return_value=opener):
            with patch.object(vpn_gate, "doh_query", return_value=["8.8.8.8"]):
                with patch.object(vpn_gate, "PinnedHTTPSConnection", side_effect=factory):
                    result = vpn_gate.https_head("example.com", 443, "/", 5)
        self.assertEqual(result, ("HTTP_RESPONSE", 403, ""))
        self.assertEqual(connections[0].args, ("example.com", "8.8.8.8", 443, 5))
        self.assertEqual(connections[0].request_args[0:2], ("HEAD", "/"))

class VPNGateDNSResolutionTests(unittest.TestCase):
    def test_a_and_aaaa_are_collected_in_one_resolver_call(self):
        infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:4860:4860::8888", 443, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.4.4", 443)),
        ]
        with patch.object(vpn_gate.socket, "getaddrinfo", return_value=infos) as resolver:
            ipv4, ipv6 = vpn_gate.resolve_domain_families("example.com", 6)
        resolver.assert_called_once_with("example.com", 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        self.assertEqual(ipv4, ("DNS_ANSWER", ["8.8.4.4", "8.8.8.8"], ""))
        self.assertEqual(ipv6, ("DNS_ANSWER", ["2001:4860:4860::8888"], ""))

    def test_dns_failure_is_reported_for_both_families(self):
        with patch.object(vpn_gate.socket, "getaddrinfo", side_effect=socket.gaierror(-2, "not found")):
            ipv4, ipv6 = vpn_gate.resolve_domain_families("missing.example", 6)
        self.assertEqual(ipv4[0], "DNS_ERROR")
        self.assertEqual(ipv6[0], "DNS_ERROR")
        self.assertIn("not found", ipv4[2])


class OpenVPNProfileSafetyTests(unittest.TestCase):
    def test_safe_tls_compatibility_directives_and_inline_tls_crypt_v2_are_preserved(self):
        config = SAMPLE_CONFIG.replace(
            "up /tmp/untrusted-up.sh",
            'tls-version-min 1.0\ntls-version-max 1.2\n'
            'tls-cipher DEFAULT:@SECLEVEL=0\n'
            'tls-ciphersuites TLS_AES_128_GCM_SHA256\n'
            'tls-cert-profile legacy\n'
            'verify-x509-name "vpn.example" name\n'
            'remote-cert-eku "TLS Web Server Authentication"\n'
            'remote-cert-ku 0x00 0x01\n'
            '<tls-crypt-v2>\n-----BEGIN OpenVPN tls-crypt-v2 client key-----\nVEVTVA==\n-----END OpenVPN tls-crypt-v2 client key-----\n</tls-crypt-v2>\n'
            'up /tmp/untrusted-up.sh'
        )
        profile = vpn_gate.inspect_openvpn_profile(config)
        server = {"server_ip": "8.8.8.8", "profile": profile}
        with tempfile.TemporaryDirectory() as directory:
            auth = pathlib.Path(directory) / "auth.txt"
            safe = vpn_gate.build_safe_openvpn_config(server, auth)
        self.assertIn("tls-version-min 1.0", safe)
        self.assertIn("tls-version-max 1.2", safe)
        self.assertIn("tls-cipher DEFAULT:@SECLEVEL=0", safe)
        self.assertIn("tls-ciphersuites TLS_AES_128_GCM_SHA256", safe)
        self.assertIn("tls-cert-profile legacy", safe)
        self.assertIn('verify-x509-name "vpn.example" name', safe)
        self.assertIn('remote-cert-eku "TLS Web Server Authentication"', safe)
        self.assertIn("remote-cert-ku 0x00 0x01", safe)
        self.assertIn("<tls-crypt-v2>", safe)
        self.assertNotIn("up /tmp", safe)
        self.assertNotIn("plugin ", safe)

    def test_profile_is_rebuilt_with_advertised_ip_and_no_untrusted_scripts(self):
        parsed = vpn_gate.inspect_openvpn_profile(SAMPLE_CONFIG)
        server = {"server_ip": "8.8.8.8", "profile": parsed}
        with tempfile.TemporaryDirectory() as directory:
            auth = pathlib.Path(directory) / "auth.txt"
            safe = vpn_gate.build_safe_openvpn_config(server, auth)
        self.assertIn("remote 8.8.8.8 443", safe)
        self.assertNotIn("old-volunteer-host", safe)
        self.assertNotIn("up /tmp", safe)
        self.assertNotIn("down /tmp", safe)
        self.assertNotIn("plugin ", safe)
        self.assertNotIn("script-security", safe)
        self.assertIn("route-nopull", safe)
        self.assertIn("redirect-gateway def1", safe)
        self.assertIn("remote-cert-tls server", safe)
        self.assertIn("<ca>", safe)
        self.assertIn("<tls-auth>", safe)
        self.assertIn("key-direction 1", safe)

    def test_non_numeric_remote_port_is_rejected(self):
        config = SAMPLE_CONFIG.replace("old-volunteer-host.opengw.net 443", "old-volunteer-host.opengw.net service")
        with self.assertRaisesRegex(ValueError, "port"):
            vpn_gate.inspect_openvpn_profile(config)

    def test_external_tls_auth_key_file_is_rejected(self):
        config = SAMPLE_CONFIG.replace(
            "<tls-auth>\n#\n# 2048 bit OpenVPN static key\n#\n"
            "-----BEGIN OpenVPN Static key V1-----\nVEVUS0VZ\n"
            "-----END OpenVPN Static key V1-----\n</tls-auth>\n",
            "tls-auth /etc/openvpn/ta.key 1\n"
        )
        with self.assertRaisesRegex(ValueError, "external key file"):
            vpn_gate.inspect_openvpn_profile(config)


    def test_profile_without_inline_ca_is_rejected(self):
        config = SAMPLE_CONFIG.replace(
            "<ca>\n-----BEGIN CERTIFICATE-----\nVEVTVENB\n-----END CERTIFICATE-----\n</ca>\n", ""
        )
        with self.assertRaisesRegex(ValueError, "CA"):
            vpn_gate.inspect_openvpn_profile(config)


    def test_firewall_snapshots_are_restored_when_killswitch_setup_fails(self):
        calls = []

        def fake_run(args, *, input_text=None, check=True):
            calls.append((args, input_text))
            if args == ["iptables-save"]:
                return subprocess.CompletedProcess(args, 0, stdout="*filter\\nCOMMIT\\n", stderr="")
            if args == ["ip6tables-save"]:
                return subprocess.CompletedProcess(args, 0, stdout="*filter\\nCOMMIT\\n", stderr="")
            if args == ["ip6tables", "-F", "OUTPUT"]:
                raise subprocess.CalledProcessError(1, args, stderr="simulated setup failure")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        guard = vpn_gate.FirewallGuard("8.8.8.8", "tcp-client", 443)
        with patch.object(vpn_gate, "run_command", side_effect=fake_run):
            with self.assertRaises(subprocess.CalledProcessError):
                guard.__enter__()

        restore_commands = [call[0][0] for call in calls if call[0][0].endswith("-restore")]
        self.assertEqual(restore_commands, ["iptables-restore", "ip6tables-restore"])





class VPNGateTimeoutRegressionTests(unittest.TestCase):
    def test_fetch_bytes_does_not_retry_pinned_https_after_socket_timeout(self):
        for failure in (
            TimeoutError("timed out"),
            urllib.error.URLError(TimeoutError("timed out")),
        ):
            opener = type("Opener", (), {
                "open": lambda self, request, timeout, error=failure: (_ for _ in ()).throw(error)
            })()
            with (
                patch.object(vpn_gate.urllib.request, "build_opener", return_value=opener),
                patch.object(vpn_gate, "call_with_wall_clock_timeout", side_effect=lambda callback, _timeout: callback()),
                patch.object(vpn_gate, "fetch_https_pinned") as pinned,
            ):
                with self.assertRaises(vpn_gate.ProbeError):
                    vpn_gate.fetch_bytes("https://metadata.example/", timeout=5)
            pinned.assert_not_called()

    def test_fetch_bytes_passes_only_remaining_budget_to_dns_fallback(self):
        opener = type("Opener", (), {
            "open": lambda self, request, timeout: (_ for _ in ()).throw(
                urllib.error.URLError(socket.gaierror("temporary resolver failure"))
            )
        })()
        with (
            patch.object(vpn_gate.urllib.request, "build_opener", return_value=opener),
            patch.object(vpn_gate.time, "monotonic", side_effect=[100.0, 105.0]),
            patch.object(vpn_gate, "call_with_wall_clock_timeout", side_effect=lambda callback, _timeout: callback()),
            patch.object(vpn_gate, "fetch_https_pinned", return_value=b"ok") as pinned,
        ):
            self.assertEqual(vpn_gate.fetch_bytes("https://metadata.example/", timeout=20), b"ok")
        pinned.assert_called_once_with("https://metadata.example/", 15.0)

    def test_https_head_does_not_start_doh_after_socket_timeout(self):
        opener = type("Opener", (), {
            "open": lambda self, request, timeout: (_ for _ in ()).throw(
                urllib.error.URLError(TimeoutError("timed out"))
            )
        })()
        with patch.object(vpn_gate.urllib.request, "build_opener", return_value=opener):
            with patch.object(vpn_gate, "doh_query") as doh:
                result = vpn_gate.https_head("target.example", 443, "/", 5)
        self.assertEqual(result[:2], ("INCONCLUSIVE", None))
        doh.assert_not_called()

    def test_ip_metadata_stops_after_two_failed_services(self):
        with patch.object(vpn_gate, "_parse_ip_metadata", side_effect=[
            vpn_gate.ProbeError("first offline"),
            vpn_gate.ProbeError("second offline"),
            {"ip": "203.0.113.10", "country": "RU"},
        ]) as lookup:
            with self.assertRaisesRegex(vpn_gate.ProbeError, "requires two independent"):
                vpn_gate.ip_metadata()
        self.assertEqual(lookup.call_count, 2)

    def test_ip_metadata_continues_after_one_failed_service_to_reach_consensus(self):
        first = {
            "ip": "203.0.113.10", "country": "RU", "asn": 1234,
            "org": "Example", "source": "second",
        }
        second = dict(first, source="third")
        with patch.object(vpn_gate, "_parse_ip_metadata", side_effect=[
            vpn_gate.ProbeError("first offline"), first, second
        ]) as lookup:
            result = vpn_gate.ip_metadata()
        self.assertEqual(result["verified_by_sources"], 2)
        self.assertEqual(result["ip"], first["ip"])
        self.assertEqual(lookup.call_count, 3)

    def test_profile_attempt_budget_has_room_for_all_30_target_probes(self):
        self.assertEqual(vpn_gate.ATTEMPT_WALL_CLOCK_BUDGET_SECONDS, 120)

    def test_attempt_budget_helper_never_extends_expired_deadline(self):
        with patch.object(vpn_gate.time, "monotonic", return_value=102.0):
            self.assertEqual(vpn_gate._bounded_remaining_seconds(105.0, 10.0), 3.0)
        with patch.object(vpn_gate.time, "monotonic", return_value=106.0):
            with self.assertRaisesRegex(TimeoutError, "budget exhausted"):
                vpn_gate._bounded_remaining_seconds(105.0, 10.0)


class VPNGateFirewallRejectTests(unittest.TestCase):
    def test_firewall_adds_explicit_reject_after_allowed_egress(self):
        calls = []

        def fake_run(args, *, input_text=None, check=True):
            calls.append(args)
            output = "*filter\\nCOMMIT\\n" if args in (["iptables-save"], ["ip6tables-save"]) else ""
            return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

        guard = vpn_gate.FirewallGuard("8.8.8.8", "tcp-client", 443)
        with patch.object(vpn_gate, "run_command", side_effect=fake_run):
            guard.__enter__()
            guard.__exit__(None, None, None)

        ipv4_reject = calls.index(["iptables", "-A", "OUTPUT", "-j", "REJECT"])
        ipv6_reject = calls.index(["ip6tables", "-A", "OUTPUT", "-j", "REJECT"])
        ipv4_tunnel_allow = calls.index(["iptables", "-A", "OUTPUT", "-o", "tun+", "-j", "ACCEPT"])
        ipv6_loopback_allow = calls.index(["ip6tables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"])
        self.assertGreater(ipv4_reject, ipv4_tunnel_allow)
        self.assertGreater(ipv6_reject, ipv6_loopback_allow)


class VPNGateReportPersistenceTests(unittest.TestCase):
    def test_sigterm_between_report_writes_is_deferred_until_all_artifacts_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            summary = {}
            real_write_tsv = vpn_gate.runner.write_tsv
            tsv_calls = []
            previous_term_handler = signal.getsignal(signal.SIGTERM)

            def write_tsv(path, rows, fields):
                tsv_calls.append(path.name)
                if len(tsv_calls) == 1:
                    os.kill(os.getpid(), signal.SIGTERM)
                return real_write_tsv(path, rows, fields)

            with patch.object(vpn_gate.runner, "write_tsv", side_effect=write_tsv):
                with self.assertRaises(SystemExit) as raised:
                    vpn_gate.persist_vpn_gate_reports(
                        output, [], [], [], [], summary
                    )

            self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)
            self.assertEqual(len(tsv_calls), 2)
            self.assertEqual(signal.getsignal(signal.SIGTERM), previous_term_handler)
            self.assertEqual(summary["report_write_errors"], [])
            self.assertTrue((output / "vpn_gate_providers.tsv").exists())
            self.assertTrue((output / "vpn_gate_measurements.jsonl").exists())
            self.assertTrue((output / "vpn_gate_geoip_candidates.tsv").exists())
            self.assertTrue((output / "vpn_gate_raw.jsonl").exists())
            self.assertTrue((output / "vpn_gate_summary.json").exists())
            self.assertFalse(any(path.name.endswith(".tmp") for path in output.iterdir()))



class VPNNetnsWrapperSignalTests(unittest.TestCase):
    def test_wrapper_waits_for_child_report_before_namespace_cleanup_on_sigterm(self):
        wrapper = pathlib.Path(__file__).resolve().parent / "vpn_netns_exec.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            fakebin = root / "bin"
            fakebin.mkdir()
            config_root = root / "netns-config"
            report_path = root / "child-report.txt"

            (fakebin / "id").write_text(chr(10).join(["#!/bin/sh", "echo 0", ""]), encoding="utf-8")
            ip_stub = """#!/bin/bash
if [[ "$1" == "-4" && "$2" == "route" && "$3" == "get" ]]; then
  echo "1.1.1.1 dev eth0"
  exit 0
fi
if [[ "$1" == "route" && "$2" == "show" ]]; then exit 0; fi
if [[ "$1" == "netns" && "$2" == "exec" ]]; then shift 3; exec "$@"; fi
if [[ "$1" == "netns" && "$2" == "pids" ]]; then exit 0; fi
exit 0
"""
            (fakebin / "ip").write_text(ip_stub, encoding="utf-8")
            for name in ("iptables", "iptables-save", "iptables-restore"):
                (fakebin / name).write_text(chr(10).join(["#!/bin/sh", "exit 0", ""]), encoding="utf-8")
            sysctl_stub = """#!/bin/sh
if [ "$1" = "-n" ]; then echo 0; fi
exit 0
"""
            (fakebin / "sysctl").write_text(sysctl_stub, encoding="utf-8")
            for path in fakebin.iterdir():
                path.chmod(0o755)

            child = (
                "trap 'sleep 0.25; printf report-complete > \"$REPORT_PATH\"; "
                "echo child_report_written; exit 0' TERM; "
                "while :; do sleep 0.05; done"
            )
            env = dict(os.environ)
            env.update({
                "PATH": str(fakebin) + os.pathsep + "/usr/bin:/bin",
                "GITHUB_RUN_ID": "999999",
                "GITHUB_RUN_ATTEMPT": "1",
                "GEOIP_VPN_NETNS_CONFIG_ROOT": str(config_root),
                "REPORT_PATH": str(report_path),
            })
            process = subprocess.Popen(
                ["bash", str(wrapper), "--", "bash", "-c", child],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            try:
                time.sleep(0.3)
                process.terminate()
                output_text, _ = process.communicate(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)

            self.assertTrue(report_path.exists(), output_text)
            self.assertIn("report-complete", report_path.read_text(encoding="utf-8"))
            self.assertLess(
                output_text.index("child_report_written"),
                output_text.index("[vpn-netns] cleanup_started"),
            )
            self.assertIn("[vpn-netns] child_exit_observed_after_signal=true", output_text)
            self.assertIn("[vpn-netns] cleanup_completed", output_text)


class VPNGateResolverSafetyTests(unittest.TestCase):
    def test_resolver_guard_never_reads_or_writes_global_resolv_conf(self):
        failure = AssertionError("global resolver config must remain untouched")
        with patch.object(pathlib.Path, "read_bytes", side_effect=failure), \
             patch.object(pathlib.Path, "write_text", side_effect=failure), \
             patch.object(pathlib.Path, "write_bytes", side_effect=failure):
            with vpn_gate.ResolverGuard():
                self.assertTrue(True)

    def test_metadata_https_fallback_does_not_try_ipv6_only_host(self):
        with patch.object(vpn_gate, "doh_query", return_value=[]) as doh:
            with patch.object(vpn_gate, "PinnedHTTPSConnection") as connection:
                with self.assertRaisesRegex(vpn_gate.ProbeError, "IPv6 HTTPS is not enabled"):
                    vpn_gate.fetch_https_pinned("https://ipv6-only.example/", 5)
        doh.assert_called_once_with("ipv6-only.example", "A", timeout=5)
        connection.assert_not_called()

    def test_target_https_fallback_does_not_try_aaaa_for_ipv6_only_host(self):
        opener = type("Opener", (), {
            "open": lambda self, request, timeout: (_ for _ in ()).throw(
                urllib.error.URLError("temporary DNS failure")
            )
        })()
        with patch.object(vpn_gate.urllib.request, "build_opener", return_value=opener):
            with patch.object(vpn_gate, "doh_query", return_value=[]) as doh:
                result = vpn_gate.https_head("ipv6-only.example", 443, "/", 5)
        self.assertEqual(result[0:2], ("INCONCLUSIVE", None))
        self.assertIn("IPv6 HTTPS is not enabled", result[2])
        doh.assert_called_once_with("ipv6-only.example", "A", timeout=5)


class VPNObrattoWallClockTimeoutTests(unittest.TestCase):
    def test_progress_manifest_records_github_run_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            progress = pathlib.Path(directory) / "progress.json"
            identity = {
                "GITHUB_SHA": "abc123",
                "GITHUB_RUN_ID": "123456",
                "GITHUB_RUN_ATTEMPT": "2",
            }
            with patch.dict(os.environ, identity):
                vpn_gate.record_vpnobratno_progress(
                    progress,
                    {"profile_index": 1, "profile_count": 1, "hostname": "vpn.example.net"},
                    "fetch_started",
                )
            manifest = json.loads(progress.read_text(encoding="utf-8"))
            self.assertEqual(manifest["execution_sha"], "abc123")
            self.assertEqual(manifest["workflow_run_id"], "123456")
            self.assertEqual(manifest["workflow_run_attempt"], "2")

    def test_wall_clock_timeout_returns_callback_result(self):
        result = vpn_gate.call_with_wall_clock_timeout(lambda: "done", 0.5)
        self.assertEqual(result, "done")

    def test_wall_clock_timeout_interrupts_a_slow_operation(self):
        started = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, "wall-clock deadline"):
            vpn_gate.call_with_wall_clock_timeout(lambda: time.sleep(0.2), 0.02)
        self.assertLess(time.monotonic() - started, 0.15)


class VPNObratnoDiscoveryTests(unittest.TestCase):
    HOST = "vpn123456789.opengw.net"

    def listing(self, links):
        return "<html><body>" + "".join(
            f'<a href="{link}">profile</a>' for link in links
        ) + "</body></html>"

    def resolver(self, hostname, *_args):
        if hostname != self.HOST:
            raise socket.gaierror("unexpected host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 1194))]

    def test_listing_accepts_only_same_origin_supported_profile_paths(self):
        valid_ip = (
            f"/servers/{self.HOST}/{self.HOST}_ip_udp.ovpn"
        )
        valid_ddns = (
            f"/servers/{self.HOST}/{self.HOST}_ddns_udp.ovpn"
        )
        links = [
            valid_ddns,
            valid_ip,
            "https://evil.example" + valid_ip,
            f"/servers/{self.HOST}/vpn999999999.opengw.net_ip_udp.ovpn",
            valid_ip + "?download=1",
            "http://vpnobratno.info" + valid_ip,
            f"/servers/{self.HOST}/{self.HOST}_l2tp_udp.ovpn",
        ]
        html = "<html>" + "".join('<a href="' + link + '">profile</a>' for link in links) + "</html>"
        profiles = vpn_gate.parse_vpnobratno_listing(html)
        self.assertEqual(
            [item["profile_variant"] for item in profiles],
            ["ip_udp", "ddns_udp"],
        )
        self.assertTrue(all(
            item["profile_url"].startswith("https://vpnobratno.info/servers/")
            for item in profiles
        ))

    def test_bounded_getent_dns_keeps_only_public_ipv4_answers(self):
        completed = subprocess.CompletedProcess(
            ["getent"], 0,
            stdout="8.8.8.8 STREAM host\\n127.0.0.1 STREAM host\\n",
            stderr="",
        )
        with patch.object(vpn_gate.subprocess, "run", return_value=completed) as run:
            answers = vpn_gate._public_ipv4_answers(self.HOST)
        self.assertEqual(answers, ["8.8.8.8"])
        self.assertEqual(run.call_args.kwargs["timeout"], 3.0)

    def test_ddns_remote_must_match_the_hostname_from_listing(self):
        address = vpn_gate.resolve_vpnobratno_server_ip(
            self.HOST, self.HOST, "ddns", self.resolver
        )
        self.assertEqual(address, "8.8.8.8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            vpn_gate.resolve_vpnobratno_server_ip(
                self.HOST, "attacker.example", "ddns", self.resolver
            )

    def test_ip_variant_uses_profile_literal_without_pre_tunnel_dns(self):
        def forbidden_resolver(*_args):
            raise AssertionError("IP profile selection must not perform DNS")
        address = vpn_gate.resolve_vpnobratno_server_ip(
            self.HOST, "8.8.8.8", "ip", forbidden_resolver
        )
        self.assertEqual(address, "8.8.8.8")
        with self.assertRaisesRegex(ValueError, "global IPv4"):
            vpn_gate.resolve_vpnobratno_server_ip(
                self.HOST, "192.168.1.1", "ip", forbidden_resolver
            )

    def test_ddns_resolution_uses_a_hard_subprocess_timeout(self):
        with patch.object(
            vpn_gate.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(["getent"], 3),
        ) as run:
            with self.assertRaisesRegex(ValueError, "bounded DNS lookup failed"):
                vpn_gate.resolve_vpnobratno_server_ip(
                    self.HOST, self.HOST, "ddns"
                )
        self.assertEqual(run.call_args.kwargs["timeout"], 3.0)
        self.assertEqual(run.call_args.args[0][:2], ["getent", "ahostsv4"])

    def test_discovery_downloads_and_validates_profiles_without_running_them(self):
        ip_udp_url = (
            f"https://vpnobratno.info/servers/{self.HOST}/{self.HOST}_ip_udp.ovpn"
        )
        ddns_udp_url = (
            f"https://vpnobratno.info/servers/{self.HOST}/{self.HOST}_ddns_udp.ovpn"
        )
        ip_config = SAMPLE_CONFIG.replace("proto tcp", "proto udp").replace(
            "remote old-volunteer-host.opengw.net 443", "remote 8.8.8.8 1194"
        )
        ddns_config = SAMPLE_CONFIG.replace("proto tcp", "proto udp").replace(
            "remote old-volunteer-host.opengw.net 443", f"remote {self.HOST} 1194"
        )
        listing = self.listing([
            ddns_udp_url.replace("https://vpnobratno.info", ""),
            ip_udp_url.replace("https://vpnobratno.info", ""),
        ]).encode()
        payloads = {
            vpn_gate.VPNOBRATNO_LIST_URL: listing,
            ip_udp_url: ip_config.encode(),
            ddns_udp_url: ddns_config.encode(),
        }
        calls = []

        def fetcher(url, timeout, max_bytes):
            calls.append((url, timeout, max_bytes))
            return payloads[url]

        servers, metadata = vpn_gate.discover_vpnobratno_servers(
            fetcher=fetcher, resolver=self.resolver
        )
        self.assertEqual(len(servers), 2)
        self.assertEqual(
            [server["profile_variant"] for server in servers],
            ["IP_UDP", "DDNS_UDP"],
        )
        self.assertEqual({server["server_ip"] for server in servers}, {"8.8.8.8"})
        self.assertTrue(all(server["source"] == "VPNOBRATNO" for server in servers))
        self.assertEqual(metadata["unique_server_hostnames"], 1)
        self.assertFalse(metadata["profile_directives_executed"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][2], vpn_gate.VPNOBRATNO_LISTING_MAX_BYTES)
        self.assertTrue(all(
            call[2] == vpn_gate.VPNOBRATNO_PROFILE_MAX_BYTES for call in calls[1:]
        ))

    def test_transport_mismatch_and_profile_for_another_host_are_skipped(self):
        ip_url = (
            f"https://vpnobratno.info/servers/{self.HOST}/{self.HOST}_ip_udp.ovpn"
        )
        config = SAMPLE_CONFIG.replace(
            "remote old-volunteer-host.opengw.net 443", "remote 8.8.8.8 1194"
        )
        listing = self.listing([
            ip_url.replace("https://vpnobratno.info", "")
        ]).encode()

        def fetcher(url, timeout, max_bytes):
            return listing if url == vpn_gate.VPNOBRATNO_LIST_URL else config.encode()

        with self.assertRaisesRegex(vpn_gate.ProbeError, "none passed validation"):
            vpn_gate.discover_vpnobratno_servers(
                fetcher=fetcher, resolver=self.resolver
            )


class VPNGateDefaultArgumentsTests(unittest.TestCase):
    def test_default_invocation_requests_one_ru_exit_and_six_profile_attempts(self):
        import os
        with patch.object(vpn_gate.sys, "argv", [
            "vpn_gate.py", "--inventory", "inventory.tsv"
        ]), patch.object(vpn_gate.shutil, "which", return_value="/usr/bin/fake"), \
             patch.object(os, "geteuid", return_value=0), \
             patch.object(vpn_gate, "run", return_value=0) as run:
            self.assertEqual(vpn_gate.main(), 0)
        args = run.call_args.args[0]
        self.assertEqual(args.source, "vpnobratno")
        self.assertEqual(args.max_servers, 1)
        self.assertEqual(args.max_attempts, 6)
        self.assertEqual(args.connect_timeout, 5)


    def test_explicit_five_second_tunnel_timeout_is_accepted(self):
        import os
        with patch.object(vpn_gate.sys, "argv", [
            "vpn_gate.py", "--inventory", "inventory.tsv",
            "--connect-timeout", "5",
        ]), patch.object(vpn_gate.shutil, "which", return_value="/usr/bin/fake"), \
             patch.object(os, "geteuid", return_value=0), \
             patch.object(vpn_gate, "run", return_value=0) as run:
            self.assertEqual(vpn_gate.main(), 0)
        args = run.call_args.args[0]
        self.assertEqual(args.connect_timeout, 5)


class VPNServerOriginCacheTests(unittest.TestCase):
    def test_measurement_report_fields_do_not_require_skipped_server_enrichment(self):
        fields = vpn_gate.server_measurement_report_fields(
            server_asn=12345,
            server_asn_ip_metadata=0,
            server_asn_ripestat=12345,
            server_asn_conflict=False,
        )
        self.assertEqual(fields, {
            "SERVER_ASN": 12345,
            "SERVER_ASN_IP_METADATA": 0,
            "SERVER_ASN_RIPESTAT": 12345,
            "SERVER_ASN_CONFLICT": False,
            "SERVER_ORG": "",
        })

    def test_selected_server_origin_uses_cached_asn_and_prefix_without_network(self):
        server = {
            "server_ip": "217.144.174.117",
            "_network_info": {"prefix": "217.144.174.0/24", "asn": 12345},
        }
        with patch.object(vpn_gate, "network_info") as network_info:
            origin = vpn_gate.cached_server_origin(server)
        self.assertEqual(origin, {"prefix": "217.144.174.0/24", "asn": 12345})
        self.assertNotIn("_network_info", server)
        network_info.assert_not_called()

    def test_selected_server_origin_missing_cache_is_empty_and_nonblocking(self):
        server = {"server_ip": "217.144.174.117"}
        with patch.object(vpn_gate, "network_info") as network_info:
            origin = vpn_gate.cached_server_origin(server)
        self.assertEqual(origin, {"prefix": "", "asn": 0})
        network_info.assert_not_called()

    def test_selected_server_origin_discards_prefix_not_containing_server_ip(self):
        server = {
            "server_ip": "203.0.113.17",
            "_network_info": {"prefix": "198.51.100.0/24", "asn": 64500},
        }
        origin = vpn_gate.cached_server_origin(server)
        self.assertEqual(origin, {"prefix": "", "asn": 64500})


class VPNObrattoFetchSafetyTests(unittest.TestCase):
    def test_redirect_handler_rejects_cross_origin_and_insecure_redirects(self):
        handler = vpn_gate.VPNObratnoSameOriginRedirect()
        request = urllib.request.Request(
            "https://vpnobratno.info/russia_server_list.html"
        )
        for target in (
            "https://evil.example/profile.ovpn",
            "https://vpnobratno.info.evil.example/profile.ovpn",
            "http://vpnobratno.info/profile.ovpn",
            "https://user@vpnobratno.info/profile.ovpn",
            "https://vpnobratno.info:8443/profile.ovpn",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(
                    vpn_gate.ProbeError, "cross-origin or insecure redirect"
                ):
                    handler.redirect_request(
                        request, None, 302, "Found", {}, target
                    )


    def test_listing_interleaves_preferred_variant_across_hosts(self):
        host_a = "vpn100000001.opengw.net"
        host_b = "vpn100000002.opengw.net"
        links = [
            f"/servers/{host_a}/{host_a}_ddns_udp.ovpn",
            f"/servers/{host_b}/{host_b}_ddns_udp.ovpn",
            f"/servers/{host_a}/{host_a}_ip_tcp.ovpn",
            f"/servers/{host_b}/{host_b}_ip_udp.ovpn",
            f"/servers/{host_a}/{host_a}_ip_udp.ovpn",
        ]
        html = "<html>" + "".join('<a href="' + link + '">profile</a>' for link in links) + "</html>"
        profiles = vpn_gate.parse_vpnobratno_listing(html)
        self.assertEqual(
            [(item["hostname"], item["profile_variant"]) for item in profiles],
            [
                (host_a, "ip_udp"),
                (host_b, "ip_udp"),
                (host_a, "ddns_udp"),
                (host_b, "ddns_udp"),
                (host_a, "ip_tcp"),
            ],
        )

    def test_discovery_limits_profile_downloads_and_reports_omitted_links(self):
        hostnames = [
            "vpn100000001.opengw.net",
            "vpn100000002.opengw.net",
            "vpn100000003.opengw.net",
            "vpn100000004.opengw.net",
        ]
        entries = [
            {
                "hostname": hostname,
                "address_mode": "ip",
                "transport": "tcp",
                "profile_variant": "ip_tcp",
                "profile_url": f"https://vpnobratno.info/servers/{hostname}/{hostname}_ip_tcp.ovpn",
            }
            for hostname in hostnames
        ]
        addresses = {
            hostname: f"8.8.8.{index}"
            for index, hostname in enumerate(hostnames, start=1)
        }

        def resolver(hostname, *_args):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addresses[hostname], 1194))]

        calls = []
        def fetcher(url, timeout, max_bytes):
            calls.append((url, max_bytes))
            if url == vpn_gate.VPNOBRATNO_LIST_URL:
                return b"<html>synthetic listing</html>"
            hostname = next(item["hostname"] for item in entries if item["profile_url"] == url)
            config = SAMPLE_CONFIG.replace(
                "remote old-volunteer-host.opengw.net 443",
                f"remote {addresses[hostname]} 1194",
            )
            return config.encode()

        with patch.object(vpn_gate, "parse_vpnobratno_listing", return_value=entries):
            servers, metadata = vpn_gate.discover_vpnobratno_servers(
                fetcher=fetcher, resolver=resolver, max_profiles=2
            )
        self.assertEqual(len(servers), 2)
        self.assertEqual(len(calls), 3)  # Listing plus two profile downloads.
        self.assertEqual(calls[0][1], vpn_gate.VPNOBRATNO_LISTING_MAX_BYTES)
        self.assertTrue(all(
            size == vpn_gate.VPNOBRATNO_PROFILE_MAX_BYTES for _, size in calls[1:]
        ))
        self.assertEqual(metadata["profile_links_found"], 4)
        self.assertEqual(metadata["profiles_considered_for_download"], 2)
        self.assertEqual(metadata["profiles_not_downloaded_due_to_limit"], 2)
        self.assertTrue(metadata["profile_download_limit_reached"])

    def test_discovery_stops_after_six_distinct_ip_profile_hosts_without_dns(self):
        hostnames = [f"vpn{100000001 + index}.opengw.net" for index in range(8)]
        entries = [
            {
                "hostname": hostname,
                "address_mode": "ip",
                "transport": "udp",
                "profile_variant": "ip_udp",
                "profile_url": f"https://vpnobratno.info/servers/{hostname}/{hostname}_ip_udp.ovpn",
            }
            for hostname in hostnames
        ]
        calls = []

        def fetcher(url, timeout, max_bytes):
            calls.append(url)
            if url == vpn_gate.VPNOBRATNO_LIST_URL:
                return b"<html>listing</html>"
            hostname = next(item["hostname"] for item in entries if item["profile_url"] == url)
            remote = f"8.8.8.{len(calls)}"
            return SAMPLE_CONFIG.replace(
                "proto tcp", "proto udp"
            ).replace(
                "remote old-volunteer-host.opengw.net 443", f"remote {remote} 1194"
            ).encode()

        def forbidden_resolver(*_args):
            raise AssertionError("IP profile discovery must not issue DNS lookups")

        with patch.object(vpn_gate, "parse_vpnobratno_listing", return_value=entries):
            servers, metadata = vpn_gate.discover_vpnobratno_servers(
                fetcher=fetcher,
                resolver=forbidden_resolver,
                max_profiles=24,
                max_unique_hosts=6,
            )

        self.assertEqual(len(servers), 6)
        self.assertEqual(len({server["hostname"] for server in servers}), 6)
        self.assertEqual(len(calls), 7)  # Listing plus six profile downloads.
        self.assertEqual(metadata["profiles_considered_for_download"], 6)
        self.assertEqual(metadata["unique_server_hostnames"], 6)
        self.assertEqual(metadata["discovery_stop_reason"], "distinct_server_host_budget_reached")
        self.assertFalse(metadata["profile_download_limit_reached"])

    def test_discovery_profile_download_limit_is_hard_capped(self):
        for value in (0, vpn_gate.VPNOBRATNO_PROFILE_DOWNLOAD_LIMIT + 1):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "max_profiles"):
                    vpn_gate.discover_vpnobratno_servers(
                        fetcher=lambda *_args, **_kwargs: b"",
                        max_profiles=value,
                    )

    def test_redirect_handler_accepts_same_https_origin_only(self):
        handler = vpn_gate.VPNObratnoSameOriginRedirect()
        request = urllib.request.Request(
            "https://vpnobratno.info/russia_server_list.html"
        )
        redirected = handler.redirect_request(
            request, None, 302, "Found", {},
            "https://vpnobratno.info/servers/example.ovpn",
        )
        self.assertEqual(
            redirected.full_url,
            "https://vpnobratno.info/servers/example.ovpn",
        )

    def test_fetcher_rejects_untrusted_input_before_opening_network(self):
        with patch.object(vpn_gate.urllib.request, "build_opener") as build_opener:
            for url in (
                "http://vpnobratno.info/profile.ovpn",
                "https://evil.example/profile.ovpn",
                "https://vpnobratno.info.evil.example/profile.ovpn",
                "https://vpnobratno.info:8443/profile.ovpn",
            ):
                with self.subTest(url=url):
                    with self.assertRaisesRegex(vpn_gate.ProbeError, "trusted HTTPS origin"):
                        vpn_gate.fetch_vpnobratno_bytes(url)
            build_opener.assert_not_called()

    def test_fetcher_enforces_response_size_during_read(self):
        class FakeResponse(io.BytesIO):
            def __init__(self, payload):
                super().__init__(payload)
                self.read_limits = []

            def geturl(self):
                return "https://vpnobratno.info/test"

            def read(self, size=-1):
                self.read_limits.append(size)
                return super().read(size)

        class FakeOpener:
            def __init__(self, response):
                self.response = response

            def open(self, request, timeout):
                return self.response

        url = "https://vpnobratno.info/test"
        exact_limit_response = FakeResponse(b"1234")
        with patch.object(
            vpn_gate.urllib.request,
            "build_opener",
            return_value=FakeOpener(exact_limit_response),
        ):
            self.assertEqual(
                vpn_gate.fetch_vpnobratno_bytes(url, max_bytes=4), b"1234"
            )
        self.assertEqual(exact_limit_response.read_limit, 5)

        oversized_response = FakeResponse(b"12345")
        with patch.object(
            vpn_gate.urllib.request,
            "build_opener",
            return_value=FakeOpener(oversized_response),
        ):
            with self.assertRaisesRegex(vpn_gate.ProbeError, "exceeds configured 4-byte limit"):
                vpn_gate.fetch_vpnobratno_bytes(url, max_bytes=4)
        self.assertEqual(oversized_response.read_limits[0], 5)

        with patch.object(vpn_gate.urllib.request, "build_opener") as build_opener:
            with self.assertRaisesRegex(ValueError, "max_bytes"):
                vpn_gate.fetch_vpnobratno_bytes(
                    url, max_bytes=vpn_gate.VPNOBRATNO_FETCH_HARD_MAX_BYTES + 1
                )
            build_opener.assert_not_called()

    def test_discovery_uses_the_same_origin_fetcher_by_default(self):
        defaults = vpn_gate.discover_vpnobratno_servers.__defaults__
        self.assertIs(defaults[0], vpn_gate.fetch_vpnobratno_bytes)



if __name__ == "__main__":
    unittest.main()
    def test_pinned_doh_answers_create_public_ipv4_hosts_overrides(self):
        answers = {
            "azure.archive.ubuntu.com": ["8.8.8.8", "10.0.0.1", "2001:4860:4860::8888"],
            "archive.ubuntu.com": ["1.1.1.1"],
            "security.ubuntu.com": ["9.9.9.9", "127.0.0.1"],
        }
        calls = []

        def resolver(hostname, record_type, timeout):
            calls.append((hostname, record_type, timeout))
            return answers[hostname]

        with tempfile.TemporaryDirectory() as directory:
            hosts_file = pathlib.Path(directory) / "hosts"
            hosts_file.write_text("127.0.0.1 localhost\n", encoding="utf-8")
            resolved = vpn_gate.install_ubuntu_apt_host_overrides(hosts_file, resolver)

            self.assertEqual(resolved, {
                "azure.archive.ubuntu.com": ["8.8.8.8"],
                "archive.ubuntu.com": ["1.1.1.1"],
                "security.ubuntu.com": ["9.9.9.9"],
            })
            contents = hosts_file.read_text(encoding="utf-8")
            self.assertIn("8.8.8.8 azure.archive.ubuntu.com", contents)
            self.assertIn("1.1.1.1 archive.ubuntu.com", contents)
            self.assertIn("9.9.9.9 security.ubuntu.com", contents)
            self.assertEqual(calls, [
                (hostname, "A", 5)
                for hostname in vpn_gate.UBUNTU_APT_MIRROR_HOSTS
            ])

            vpn_gate.install_ubuntu_apt_host_overrides(hosts_file, resolver)
            self.assertEqual(
                hosts_file.read_text(encoding="utf-8").count(vpn_gate.APT_HOSTS_BLOCK_START),
                1,
            )

    def test_doh_failure_does_not_write_a_partial_hosts_override(self):
        with tempfile.TemporaryDirectory() as directory:
            hosts_file = pathlib.Path(directory) / "hosts"
            original = "127.0.0.1 localhost\n"
            hosts_file.write_text(original, encoding="utf-8")

            def resolver(hostname, record_type, timeout):
                if hostname == "security.ubuntu.com":
                    raise vpn_gate.ProbeError("resolver unavailable")
                return ["8.8.8.8"]

            with self.assertRaisesRegex(vpn_gate.ProbeError, "security.ubuntu.com"):
                vpn_gate.install_ubuntu_apt_host_overrides(hosts_file, resolver)
            self.assertEqual(hosts_file.read_text(encoding="utf-8"), original)

    def test_invalid_hosts_file_markers_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            hosts_file = pathlib.Path(directory) / "hosts"
            hosts_file.write_text(
                "127.0.0.1 localhost\n" + vpn_gate.APT_HOSTS_BLOCK_START + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(vpn_gate.ProbeError, "inconsistent"):
                vpn_gate.install_ubuntu_apt_host_overrides(
                    hosts_file,
                    lambda hostname, record_type, timeout: ["8.8.8.8"],
                )


class VPNGateDoHTests(unittest.TestCase):
    def test_doh_query_uses_pinned_resolver_and_filters_requested_type(self):
        class FakeSocket:
            def __init__(self):
                self.timeouts = []
            def settimeout(self, value):
                self.timeouts.append(value)

        class FakeResponse:
            status = 200
            def __init__(self, sock):
                self.fp = type("FakeFP", (), {
                    "raw": type("FakeRaw", (), {"_sock": sock})()
                })()
                self.payload = json.dumps({
                    "Status": 0,
                    "Answer": [
                        {"type": 1, "data": "8.8.8.8"},
                        {"type": 28, "data": "2001:4860:4860::8888"},
                        {"type": 1, "data": "10.0.0.1"},
                    ],
                }).encode()
                self.read = False
            def read1(self, limit):
                if self.read:
                    return b""
                self.read = True
                return self.payload[:limit]

        class FakeConnection:
            def __init__(self, host, address, timeout):
                self.host, self.address, self.timeout = host, address, timeout
                self.request_args = None
                self.sock = FakeSocket()
            def request(self, method, path, headers):
                self.request_args = (method, path, headers)
            def getresponse(self):
                return FakeResponse(self.sock)
            def close(self):
                pass

        made = []
        def factory(host, address, timeout):
            connection = FakeConnection(host, address, timeout)
            made.append(connection)
            return connection

        with patch.object(vpn_gate, "PinnedHTTPSConnection", side_effect=factory):
            result = vpn_gate.doh_query("example.com", "A")
        self.assertEqual(result, ["8.8.8.8"])
        self.assertEqual(made[0].host, "cloudflare-dns.com")
        self.assertEqual(made[0].address, "1.1.1.1")
        self.assertIn("type=A", made[0].request_args[1])
        self.assertGreaterEqual(len(made[0].sock.timeouts), 2)

    def test_doh_query_enforces_one_absolute_deadline_during_slow_drip(self):
        clock = [0.0]
        made = []

        class FakeSocket:
            def __init__(self):
                self.timeouts = []
            def settimeout(self, value):
                self.timeouts.append(value)

        class SlowResponse:
            status = 200
            def __init__(self, sock):
                self.fp = type("FakeFP", (), {
                    "raw": type("FakeRaw", (), {"_sock": sock})()
                })()
                self.reads = 0
            def read1(self, _limit):
                self.reads += 1
                clock[0] += 0.6
                return b"x"

        class FakeConnection:
            def __init__(self, host, address, timeout):
                self.host, self.address, self.timeout = host, address, timeout
                self.sock = FakeSocket()
                self.response = SlowResponse(self.sock)
                made.append(self)
            def request(self, *_args, **_kwargs):
                pass
            def getresponse(self):
                return self.response
            def close(self):
                pass

        with patch.object(vpn_gate.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(vpn_gate, "PinnedHTTPSConnection", side_effect=FakeConnection):
            with self.assertRaisesRegex(vpn_gate.ProbeError, "all pinned DNS-over-HTTPS resolvers failed"):
                vpn_gate.doh_query("example.com", "A", timeout=1)

        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].response.reads, 2)
        self.assertGreaterEqual(len(made[0].sock.timeouts), 3)
        self.assertLess(made[0].sock.timeouts[-1], made[0].sock.timeouts[0])

    def test_doh_query_does_not_retry_after_outer_alarm_timeout(self):
        clock = [0.0]
        made = []

        class FakeSocket:
            def settimeout(self, _value):
                pass

        class AlarmResponse:
            status = 200
            def __init__(self, sock):
                self.fp = type("FakeFP", (), {
                    "raw": type("FakeRaw", (), {"_sock": sock})()
                })()
            def read1(self, _limit):
                clock[0] = 1.1
                raise TimeoutError("wall-clock deadline")

        class FakeConnection:
            def __init__(self, host, address, timeout):
                self.host, self.address, self.timeout = host, address, timeout
                self.sock = FakeSocket()
                self.response = AlarmResponse(self.sock)
                made.append(self)
            def request(self, *_args, **_kwargs):
                pass
            def getresponse(self):
                return self.response
            def close(self):
                pass

        with (
            patch.object(vpn_gate.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(vpn_gate, "PinnedHTTPSConnection", side_effect=FakeConnection),
        ):
            with self.assertRaisesRegex(vpn_gate.ProbeError, "all pinned DNS-over-HTTPS resolvers failed"):
                vpn_gate.doh_query("example.com", "A", timeout=1)

        self.assertEqual(len(made), 1)

    def test_system_dns_failure_falls_back_to_pinned_doh_for_both_families(self):
        with patch.object(vpn_gate.socket, "getaddrinfo", side_effect=socket.gaierror(-3, "temporary failure")):
            with patch.object(vpn_gate, "doh_query", side_effect=[
                ["8.8.8.8"], ["2001:4860:4860::8888"]
            ]) as doh:
                ipv4, ipv6 = vpn_gate.resolve_domain_families("example.com", 5)
        self.assertEqual(ipv4, ("DNS_ANSWER", ["8.8.8.8"], ""))
        self.assertEqual(ipv6, ("DNS_ANSWER", ["2001:4860:4860::8888"], ""))
        self.assertEqual([call.args[1] for call in doh.call_args_list], ["A", "AAAA"])

    def test_metadata_fetch_uses_pinned_https_when_system_dns_fails(self):
        opener = type("Opener", (), {
            "open": lambda self, request, timeout: (_ for _ in ()).throw(
                urllib.error.URLError("temporary DNS failure")
            )
        })()
        with patch.object(vpn_gate.urllib.request, "build_opener", return_value=opener):
            with patch.object(vpn_gate, "fetch_https_pinned", return_value=b'{"ip":"8.8.8.8"}') as pinned:
                payload = vpn_gate.fetch_bytes("https://ipwho.is/", timeout=5)
        self.assertEqual(payload, b'{"ip":"8.8.8.8"}')
        pinned.assert_called_once_with("https://ipwho.is/", 5)


    def test_https_head_uses_pinned_sni_fallback_after_system_dns_failure(self):
        opener = type("Opener", (), {
            "open": lambda self, request, timeout: (_ for _ in ()).throw(
                urllib.error.URLError("temporary DNS failure")
            )
        })()

        class FakeResponse:
            status = 403
            def read(self, limit):
                return b""

        class FakeConnection:
            def __init__(self, host, address, port, timeout):
                self.args = (host, address, port, timeout)
                self.request_args = None
            def request(self, method, path, headers):
                self.request_args = (method, path, headers)
            def getresponse(self):
                return FakeResponse()
            def close(self):
                pass

        connections = []
        def factory(host, address, port, timeout):
            connection = FakeConnection(host, address, port, timeout)
            connections.append(connection)
            return connection

        with patch.object(vpn_gate.urllib.request, "build_opener", return_value=opener):
            with patch.object(vpn_gate, "doh_query", return_value=["8.8.8.8"]):
                with patch.object(vpn_gate, "PinnedHTTPSConnection", side_effect=factory):
                    result = vpn_gate.https_head("example.com", 443, "/", 5)
        self.assertEqual(result, ("HTTP_RESPONSE", 403, ""))
        self.assertEqual(connections[0].args, ("example.com", "8.8.8.8", 443, 5))
        self.assertEqual(connections[0].request_args[0:2], ("HEAD", "/"))

class VPNGateDNSResolutionTests(unittest.TestCase):
    def test_a_and_aaaa_are_collected_in_one_resolver_call(self):
        infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:4860:4860::8888", 443, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.4.4", 443)),
        ]
        with patch.object(vpn_gate.socket, "getaddrinfo", return_value=infos) as resolver:
            ipv4, ipv6 = vpn_gate.resolve_domain_families("example.com", 6)
        resolver.assert_called_once_with("example.com", 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        self.assertEqual(ipv4, ("DNS_ANSWER", ["8.8.4.4", "8.8.8.8"], ""))
        self.assertEqual(ipv6, ("DNS_ANSWER", ["2001:4860:4860::8888"], ""))

    def test_dns_failure_is_reported_for_both_families(self):
        with patch.object(vpn_gate.socket, "getaddrinfo", side_effect=socket.gaierror(-2, "not found")):
            ipv4, ipv6 = vpn_gate.resolve_domain_families("missing.example", 6)
        self.assertEqual(ipv4[0], "DNS_ERROR")
        self.assertEqual(ipv6[0], "DNS_ERROR")
        self.assertIn("not found", ipv4[2])


class OpenVPNProfileSafetyTests(unittest.TestCase):
    def test_safe_tls_compatibility_directives_and_inline_tls_crypt_v2_are_preserved(self):
        config = SAMPLE_CONFIG.replace(
            "up /tmp/untrusted-up.sh",
            'tls-version-min 1.0\ntls-version-max 1.2\n'
            'tls-cipher DEFAULT:@SECLEVEL=0\n'
            'tls-ciphersuites TLS_AES_128_GCM_SHA256\n'
            'tls-cert-profile legacy\n'
            'verify-x509-name "vpn.example" name\n'
            'remote-cert-eku "TLS Web Server Authentication"\n'
            'remote-cert-ku 0x00 0x01\n'
            '<tls-crypt-v2>\n-----BEGIN OpenVPN tls-crypt-v2 client key-----\nVEVTVA==\n-----END OpenVPN tls-crypt-v2 client key-----\n</tls-crypt-v2>\n'
            'up /tmp/untrusted-up.sh'
        )
        profile = vpn_gate.inspect_openvpn_profile(config)
        server = {"server_ip": "8.8.8.8", "profile": profile}
        with tempfile.TemporaryDirectory() as directory:
            auth = pathlib.Path(directory) / "auth.txt"
            safe = vpn_gate.build_safe_openvpn_config(server, auth)
        self.assertIn("tls-version-min 1.0", safe)
        self.assertIn("tls-version-max 1.2", safe)
        self.assertIn("tls-cipher DEFAULT:@SECLEVEL=0", safe)
        self.assertIn("tls-ciphersuites TLS_AES_128_GCM_SHA256", safe)
        self.assertIn("tls-cert-profile legacy", safe)
        self.assertIn('verify-x509-name "vpn.example" name', safe)
        self.assertIn('remote-cert-eku "TLS Web Server Authentication"', safe)
        self.assertIn("remote-cert-ku 0x00 0x01", safe)
        self.assertIn("<tls-crypt-v2>", safe)
        self.assertNotIn("up /tmp", safe)
        self.assertNotIn("plugin ", safe)

    def test_profile_is_rebuilt_with_advertised_ip_and_no_untrusted_scripts(self):
        parsed = vpn_gate.inspect_openvpn_profile(SAMPLE_CONFIG)
        server = {"server_ip": "8.8.8.8", "profile": parsed}
        with tempfile.TemporaryDirectory() as directory:
            auth = pathlib.Path(directory) / "auth.txt"
            safe = vpn_gate.build_safe_openvpn_config(server, auth)
        self.assertIn("remote 8.8.8.8 443", safe)
        self.assertNotIn("old-volunteer-host", safe)
        self.assertNotIn("up /tmp", safe)
        self.assertNotIn("down /tmp", safe)
        self.assertNotIn("plugin ", safe)
        self.assertNotIn("script-security", safe)
        self.assertIn("route-nopull", safe)
        self.assertIn("redirect-gateway def1", safe)
        self.assertIn("remote-cert-tls server", safe)
        self.assertIn("<ca>", safe)
        self.assertIn("<tls-auth>", safe)
        self.assertIn("key-direction 1", safe)

    def test_non_numeric_remote_port_is_rejected(self):
        config = SAMPLE_CONFIG.replace("old-volunteer-host.opengw.net 443", "old-volunteer-host.opengw.net service")
        with self.assertRaisesRegex(ValueError, "port"):
            vpn_gate.inspect_openvpn_profile(config)

    def test_external_tls_auth_key_file_is_rejected(self):
        config = SAMPLE_CONFIG.replace(
            "<tls-auth>\n#\n# 2048 bit OpenVPN static key\n#\n"
            "-----BEGIN OpenVPN Static key V1-----\nVEVUS0VZ\n"
            "-----END OpenVPN Static key V1-----\n</tls-auth>\n",
            "tls-auth /etc/openvpn/ta.key 1\n"
        )
        with self.assertRaisesRegex(ValueError, "external key file"):
            vpn_gate.inspect_openvpn_profile(config)


    def test_profile_without_inline_ca_is_rejected(self):
        config = SAMPLE_CONFIG.replace(
            "<ca>\n-----BEGIN CERTIFICATE-----\nVEVTVENB\n-----END CERTIFICATE-----\n</ca>\n", ""
        )
        with self.assertRaisesRegex(ValueError, "CA"):
            vpn_gate.inspect_openvpn_profile(config)


    def test_firewall_snapshots_are_restored_when_killswitch_setup_fails(self):
        calls = []

        def fake_run(args, *, input_text=None, check=True):
            calls.append((args, input_text))
            if args == ["iptables-save"]:
                return subprocess.CompletedProcess(args, 0, stdout="*filter\\nCOMMIT\\n", stderr="")
            if args == ["ip6tables-save"]:
                return subprocess.CompletedProcess(args, 0, stdout="*filter\\nCOMMIT\\n", stderr="")
            if args == ["ip6tables", "-F", "OUTPUT"]:
                raise subprocess.CalledProcessError(1, args, stderr="simulated setup failure")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        guard = vpn_gate.FirewallGuard("8.8.8.8", "tcp-client", 443)
        with patch.object(vpn_gate, "run_command", side_effect=fake_run):
            with self.assertRaises(subprocess.CalledProcessError):
                guard.__enter__()

        restore_commands = [call[0][0] for call in calls if call[0][0].endswith("-restore")]
        self.assertEqual(restore_commands, ["iptables-restore", "ip6tables-restore"])


class VPNGateResolverSafetyTests(unittest.TestCase):
    def test_resolver_guard_never_reads_or_writes_global_resolv_conf(self):
        failure = AssertionError("global resolver config must remain untouched")
        with patch.object(pathlib.Path, "read_bytes", side_effect=failure), \
             patch.object(pathlib.Path, "write_text", side_effect=failure), \
             patch.object(pathlib.Path, "write_bytes", side_effect=failure):
            with vpn_gate.ResolverGuard():
                self.assertTrue(True)

    def test_metadata_https_fallback_does_not_try_ipv6_only_host(self):
        with patch.object(vpn_gate, "doh_query", return_value=[]) as doh:
            with patch.object(vpn_gate, "PinnedHTTPSConnection") as connection:
                with self.assertRaisesRegex(vpn_gate.ProbeError, "IPv6 HTTPS is not enabled"):
                    vpn_gate.fetch_https_pinned("https://ipv6-only.example/", 5)
        doh.assert_called_once_with("ipv6-only.example", "A", timeout=5)
        connection.assert_not_called()

    def test_target_https_fallback_does_not_try_aaaa_for_ipv6_only_host(self):
        opener = type("Opener", (), {
            "open": lambda self, request, timeout: (_ for _ in ()).throw(
                urllib.error.URLError("temporary DNS failure")
            )
        })()
        with patch.object(vpn_gate.urllib.request, "build_opener", return_value=opener):
            with patch.object(vpn_gate, "doh_query", return_value=[]) as doh:
                result = vpn_gate.https_head("ipv6-only.example", 443, "/", 5)
        self.assertEqual(result[0:2], ("INCONCLUSIVE", None))
        self.assertIn("IPv6 HTTPS is not enabled", result[2])
        doh.assert_called_once_with("ipv6-only.example", "A", timeout=5)


class VPNObrattoWallClockTimeoutTests(unittest.TestCase):
    def test_wall_clock_timeout_returns_callback_result(self):
        result = vpn_gate.call_with_wall_clock_timeout(lambda: "done", 0.5)
        self.assertEqual(result, "done")

    def test_wall_clock_timeout_interrupts_a_slow_operation(self):
        started = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, "wall-clock deadline"):
            vpn_gate.call_with_wall_clock_timeout(lambda: time.sleep(0.2), 0.02)
        self.assertLess(time.monotonic() - started, 0.15)


    def test_progress_manifest_uses_atomic_replace_without_per_event_fsync(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = pathlib.Path(tmp) / "vpn_gate_vpnobratto_progress.json"
            context = {
                "profile_index": 6,
                "profile_count": 24,
                "hostname": "vpn950792227.opengw.net",
                "variant": "ip_udp",
                "address_mode": "ip",
            }
            with patch.object(
                vpn_gate.os,
                "fsync",
                side_effect=AssertionError("per-phase manifest updates must not fsync"),
            ) as fsync:
                vpn_gate.record_vpnobratno_progress(
                    manifest,
                    context,
                    "profile_https.body_read_completed",
                    elapsed_ms=534,
                    total_bytes=3830,
                )
            fsync.assert_not_called()
            data = json.loads(manifest.read_text(encoding="utf-8"))
            record = data["profiles"]["6"]
            self.assertEqual(record["state"], "profile_https.body_read_completed")
            self.assertEqual(record["total_bytes"], 3830)
            self.assertEqual(data["last_event"]["profile"], "6")
            self.assertTrue(manifest.exists())


    def test_isolated_fetch_worker_returns_payload_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = pathlib.Path(tmp) / "vpnobratto_progress.json"
            context = {
                "profile_index": 3,
                "profile_count": 6,
                "hostname": "vpn123456789.opengw.net",
                "variant": "ip_udp",
                "address_mode": "ip",
            }
            payload = vpn_gate.fetch_vpnobratno_in_worker(
                _vpnobratto_worker_test_success,
                "https://vpnobratno.info/profile.ovpn",
                timeout=2,
                fetch_timeout=12,
                max_bytes=64000,
                context=context,
                progress_path=manifest,
            )
            self.assertEqual(
                payload,
                b"https://vpnobratno.info/profile.ovpn|12|64000",
            )
            data = json.loads(manifest.read_text(encoding="utf-8"))
            profile = data["profiles"]["3"]
            self.assertEqual(profile["state"], "worker_completed")
            self.assertEqual(profile["hostname"], context["hostname"])
            event_names = [item["event"] for item in profile["events"]]
            self.assertIn("supervisor_starting", event_names)
            self.assertIn("worker_started", event_names)
            self.assertIn("worker.payload_ready", event_names)
            self.assertIn("worker_completed", event_names)
            self.assertEqual(data["execution_sha"], os.environ.get("GITHUB_SHA", ""))

    def test_isolated_fetch_worker_reports_early_child_exit_separately_from_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = pathlib.Path(tmp) / "vpnobratto_progress.json"
            context = {
                "profile_index": 4,
                "profile_count": 6,
                "hostname": "vpn555555555.opengw.net",
                "variant": "ip_udp",
                "address_mode": "ip",
            }
            with self.assertRaisesRegex(
                vpn_gate.ProbeError, "ended without a result"
            ):
                vpn_gate.fetch_vpnobratno_in_worker(
                    _vpnobratto_worker_test_crash,
                    "synthetic-crash",
                    timeout=2,
                    fetch_timeout=12,
                    max_bytes=64000,
                    context=context,
                    progress_path=manifest,
                )
            data = json.loads(manifest.read_text(encoding="utf-8"))
            record = data["profiles"]["4"]
            self.assertEqual(record["state"], "worker_failed_without_result")
            failure_event = record["events"][-1]
            self.assertIn(
                failure_event["reason"],
                {"pipe_eof", "pipe_eof_after_worker_exit", "worker_exited_without_message"},
            )
            self.assertEqual(failure_event["worker_exitcode"], 17)
            self.assertNotEqual(failure_event["reason"], "worker_deadline_expired")

    def test_isolated_fetch_worker_kills_term_resistant_child_at_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            pid_file = pathlib.Path(tmp) / "worker.pid"
            manifest = pathlib.Path(tmp) / "vpnobratto_progress.json"
            context = {
                "profile_index": 6,
                "profile_count": 24,
                "hostname": "vpn987654321.opengw.net",
                "variant": "ip_udp",
                "address_mode": "ip",
            }
            started = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, "isolated fetch exceeded"):
                vpn_gate.fetch_vpnobratno_in_worker(
                    _vpnobratto_worker_test_hang,
                    str(pid_file),
                    timeout=0.25,
                    fetch_timeout=12,
                    max_bytes=64000,
                    context=context,
                    progress_path=manifest,
                )
            self.assertLess(time.monotonic() - started, 2.0)
            self.assertTrue(pid_file.exists())
            worker_pid = int(pid_file.read_text(encoding="ascii"))
            with self.assertRaises(ProcessLookupError):
                os.kill(worker_pid, 0)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            profile = data["profiles"]["6"]
            self.assertEqual(profile["state"], "worker_timeout")
            timeout_event = profile["events"][-1]
            self.assertTrue(timeout_event["term_sent"])
            self.assertTrue(timeout_event["kill_sent"])
            self.assertEqual(timeout_event["worker_exitcode"], -signal.SIGKILL)


class VPNObratnoDiscoveryTests(unittest.TestCase):
    HOST = "vpn123456789.opengw.net"

    def listing(self, links):
        return "<html><body>" + "".join(
            f'<a href="{link}">profile</a>' for link in links
        ) + "</body></html>"

    def resolver(self, hostname, *_args):
        if hostname != self.HOST:
            raise socket.gaierror("unexpected host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 1194))]

    def test_listing_accepts_only_same_origin_supported_profile_paths(self):
        valid_ip = (
            f"/servers/{self.HOST}/{self.HOST}_ip_udp.ovpn"
        )
        valid_ddns = (
            f"/servers/{self.HOST}/{self.HOST}_ddns_udp.ovpn"
        )
        links = [
            valid_ddns,
            valid_ip,
            "https://evil.example" + valid_ip,
            f"/servers/{self.HOST}/vpn999999999.opengw.net_ip_udp.ovpn",
            valid_ip + "?download=1",
            "http://vpnobratno.info" + valid_ip,
            f"/servers/{self.HOST}/{self.HOST}_l2tp_udp.ovpn",
        ]
        html = "<html>" + "".join('<a href="' + link + '">profile</a>' for link in links) + "</html>"
        profiles = vpn_gate.parse_vpnobratno_listing(html)
        self.assertEqual(
            [item["profile_variant"] for item in profiles],
            ["ip_udp", "ddns_udp"],
        )
        self.assertTrue(all(
            item["profile_url"].startswith("https://vpnobratno.info/servers/")
            for item in profiles
        ))

    def test_bounded_getent_dns_keeps_only_public_ipv4_answers(self):
        completed = subprocess.CompletedProcess(
            ["getent"], 0,
            stdout="8.8.8.8 STREAM host\\n127.0.0.1 STREAM host\\n",
            stderr="",
        )
        with patch.object(vpn_gate.subprocess, "run", return_value=completed) as run:
            answers = vpn_gate._public_ipv4_answers(self.HOST)
        self.assertEqual(answers, ["8.8.8.8"])
        self.assertEqual(run.call_args.kwargs["timeout"], 3.0)

    def test_ddns_remote_must_match_the_hostname_from_listing(self):
        address = vpn_gate.resolve_vpnobratno_server_ip(
            self.HOST, self.HOST, "ddns", self.resolver
        )
        self.assertEqual(address, "8.8.8.8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            vpn_gate.resolve_vpnobratno_server_ip(
                self.HOST, "attacker.example", "ddns", self.resolver
            )

    def test_ip_variant_uses_profile_literal_without_pre_tunnel_dns(self):
        def forbidden_resolver(*_args):
            raise AssertionError("IP profile selection must not perform DNS")
        address = vpn_gate.resolve_vpnobratno_server_ip(
            self.HOST, "8.8.8.8", "ip", forbidden_resolver
        )
        self.assertEqual(address, "8.8.8.8")
        with self.assertRaisesRegex(ValueError, "global IPv4"):
            vpn_gate.resolve_vpnobratno_server_ip(
                self.HOST, "192.168.1.1", "ip", forbidden_resolver
            )

    def test_ddns_resolution_uses_a_hard_subprocess_timeout(self):
        with patch.object(
            vpn_gate.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(["getent"], 3),
        ) as run:
            with self.assertRaisesRegex(ValueError, "bounded DNS lookup failed"):
                vpn_gate.resolve_vpnobratno_server_ip(
                    self.HOST, self.HOST, "ddns"
                )
        self.assertEqual(run.call_args.kwargs["timeout"], 3.0)
        self.assertEqual(run.call_args.args[0][:2], ["getent", "ahostsv4"])

    def test_default_fetcher_is_run_in_a_separate_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = pathlib.Path(tmp) / "vpnobratto_progress.json"
            with patch.object(
                vpn_gate,
                "fetch_vpnobratno_in_worker",
                return_value=b"<html><body></body></html>",
            ) as worker:
                with self.assertRaisesRegex(
                    vpn_gate.ProbeError, "contains no supported OpenVPN profile links"
                ):
                    vpn_gate.discover_vpnobratno_servers(
                        max_profiles=1,
                        progress_path=manifest,
                    )
            worker.assert_called_once()
            args, kwargs = worker.call_args
            self.assertIs(args[0], vpn_gate.fetch_vpnobratno_bytes)
            self.assertEqual(kwargs["timeout"], 20)
            self.assertEqual(kwargs["fetch_timeout"], 15)
            self.assertEqual(kwargs["context"]["variant"], "listing")
            self.assertEqual(kwargs["progress_path"], manifest)

    def test_discovery_downloads_and_validates_profiles_without_running_them(self):
        ip_udp_url = (
            f"https://vpnobratno.info/servers/{self.HOST}/{self.HOST}_ip_udp.ovpn"
        )
        ddns_udp_url = (
            f"https://vpnobratno.info/servers/{self.HOST}/{self.HOST}_ddns_udp.ovpn"
        )
        ip_config = SAMPLE_CONFIG.replace("proto tcp", "proto udp").replace(
            "remote old-volunteer-host.opengw.net 443", "remote 8.8.8.8 1194"
        )
        ddns_config = SAMPLE_CONFIG.replace("proto tcp", "proto udp").replace(
            "remote old-volunteer-host.opengw.net 443", f"remote {self.HOST} 1194"
        )
        listing = self.listing([
            ddns_udp_url.replace("https://vpnobratno.info", ""),
            ip_udp_url.replace("https://vpnobratno.info", ""),
        ]).encode()
        payloads = {
            vpn_gate.VPNOBRATNO_LIST_URL: listing,
            ip_udp_url: ip_config.encode(),
            ddns_udp_url: ddns_config.encode(),
        }
        calls = []

        def fetcher(url, timeout, max_bytes):
            calls.append((url, timeout, max_bytes))
            return payloads[url]

        servers, metadata = vpn_gate.discover_vpnobratno_servers(
            fetcher=fetcher, resolver=self.resolver
        )
        self.assertEqual(len(servers), 2)
        self.assertEqual(
            [server["profile_variant"] for server in servers],
            ["IP_UDP", "DDNS_UDP"],
        )
        self.assertEqual({server["server_ip"] for server in servers}, {"8.8.8.8"})
        self.assertTrue(all(server["source"] == "VPNOBRATNO" for server in servers))
        self.assertEqual(metadata["unique_server_hostnames"], 1)
        self.assertFalse(metadata["profile_directives_executed"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][2], vpn_gate.VPNOBRATNO_LISTING_MAX_BYTES)
        self.assertTrue(all(
            call[2] == vpn_gate.VPNOBRATNO_PROFILE_MAX_BYTES for call in calls[1:]
        ))

    def test_transport_mismatch_and_profile_for_another_host_are_skipped(self):
        ip_url = (
            f"https://vpnobratno.info/servers/{self.HOST}/{self.HOST}_ip_udp.ovpn"
        )
        config = SAMPLE_CONFIG.replace(
            "remote old-volunteer-host.opengw.net 443", "remote 8.8.8.8 1194"
        )
        listing = self.listing([
            ip_url.replace("https://vpnobratno.info", "")
        ]).encode()

        def fetcher(url, timeout, max_bytes):
            return listing if url == vpn_gate.VPNOBRATNO_LIST_URL else config.encode()

        with self.assertRaisesRegex(vpn_gate.ProbeError, "none passed validation"):
            vpn_gate.discover_vpnobratno_servers(
                fetcher=fetcher, resolver=self.resolver
            )


class VPNGateDefaultArgumentsTests(unittest.TestCase):
    def test_default_invocation_requests_one_ru_exit_and_six_profile_attempts(self):
        import os
        with patch.object(vpn_gate.sys, "argv", [
            "vpn_gate.py", "--inventory", "inventory.tsv"
        ]), patch.object(vpn_gate.shutil, "which", return_value="/usr/bin/fake"), \
             patch.object(os, "geteuid", return_value=0), \
             patch.object(vpn_gate, "run", return_value=0) as run:
            self.assertEqual(vpn_gate.main(), 0)
        args = run.call_args.args[0]
        self.assertEqual(args.source, "vpnobratno")
        self.assertEqual(args.max_servers, 1)
        self.assertEqual(args.max_attempts, 6)
        self.assertEqual(args.connect_timeout, 5)


    def test_explicit_five_second_tunnel_timeout_is_accepted(self):
        import os
        with patch.object(vpn_gate.sys, "argv", [
            "vpn_gate.py", "--inventory", "inventory.tsv",
            "--connect-timeout", "5",
        ]), patch.object(vpn_gate.shutil, "which", return_value="/usr/bin/fake"), \
             patch.object(os, "geteuid", return_value=0), \
             patch.object(vpn_gate, "run", return_value=0) as run:
            self.assertEqual(vpn_gate.main(), 0)
        args = run.call_args.args[0]
        self.assertEqual(args.connect_timeout, 5)


class VPNServerOriginCacheTests(unittest.TestCase):
    def test_measurement_report_fields_do_not_require_skipped_server_enrichment(self):
        fields = vpn_gate.server_measurement_report_fields(
            server_asn=12345,
            server_asn_ip_metadata=0,
            server_asn_ripestat=12345,
            server_asn_conflict=False,
        )
        self.assertEqual(fields, {
            "SERVER_ASN": 12345,
            "SERVER_ASN_IP_METADATA": 0,
            "SERVER_ASN_RIPESTAT": 12345,
            "SERVER_ASN_CONFLICT": False,
            "SERVER_ORG": "",
        })

    def test_selected_server_origin_uses_cached_asn_and_prefix_without_network(self):
        server = {
            "server_ip": "217.144.174.117",
            "_network_info": {"prefix": "217.144.174.0/24", "asn": 12345},
        }
        with patch.object(vpn_gate, "network_info") as network_info:
            origin = vpn_gate.cached_server_origin(server)
        self.assertEqual(origin, {"prefix": "217.144.174.0/24", "asn": 12345})
        self.assertNotIn("_network_info", server)
        network_info.assert_not_called()

    def test_selected_server_origin_missing_cache_is_empty_and_nonblocking(self):
        server = {"server_ip": "217.144.174.117"}
        with patch.object(vpn_gate, "network_info") as network_info:
            origin = vpn_gate.cached_server_origin(server)
        self.assertEqual(origin, {"prefix": "", "asn": 0})
        network_info.assert_not_called()

    def test_selected_server_origin_discards_prefix_not_containing_server_ip(self):
        server = {
            "server_ip": "203.0.113.17",
            "_network_info": {"prefix": "198.51.100.0/24", "asn": 64500},
        }
        origin = vpn_gate.cached_server_origin(server)
        self.assertEqual(origin, {"prefix": "", "asn": 64500})


class VPNObrattoFetchSafetyTests(unittest.TestCase):
    def test_redirect_handler_rejects_cross_origin_and_insecure_redirects(self):
        handler = vpn_gate.VPNObratnoSameOriginRedirect()
        request = urllib.request.Request(
            "https://vpnobratno.info/russia_server_list.html"
        )
        for target in (
            "https://evil.example/profile.ovpn",
            "https://vpnobratno.info.evil.example/profile.ovpn",
            "http://vpnobratno.info/profile.ovpn",
            "https://user@vpnobratno.info/profile.ovpn",
            "https://vpnobratno.info:8443/profile.ovpn",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(
                    vpn_gate.ProbeError, "cross-origin or insecure redirect"
                ):
                    handler.redirect_request(
                        request, None, 302, "Found", {}, target
                    )


    def test_listing_interleaves_preferred_variant_across_hosts(self):
        host_a = "vpn100000001.opengw.net"
        host_b = "vpn100000002.opengw.net"
        links = [
            f"/servers/{host_a}/{host_a}_ddns_udp.ovpn",
            f"/servers/{host_b}/{host_b}_ddns_udp.ovpn",
            f"/servers/{host_a}/{host_a}_ip_tcp.ovpn",
            f"/servers/{host_b}/{host_b}_ip_udp.ovpn",
            f"/servers/{host_a}/{host_a}_ip_udp.ovpn",
        ]
        html = "<html>" + "".join('<a href="' + link + '">profile</a>' for link in links) + "</html>"
        profiles = vpn_gate.parse_vpnobratno_listing(html)
        self.assertEqual(
            [(item["hostname"], item["profile_variant"]) for item in profiles],
            [
                (host_a, "ip_udp"),
                (host_b, "ip_udp"),
                (host_a, "ddns_udp"),
                (host_b, "ddns_udp"),
                (host_a, "ip_tcp"),
            ],
        )

    def test_discovery_limits_profile_downloads_and_reports_omitted_links(self):
        hostnames = [
            "vpn100000001.opengw.net",
            "vpn100000002.opengw.net",
            "vpn100000003.opengw.net",
            "vpn100000004.opengw.net",
        ]
        entries = [
            {
                "hostname": hostname,
                "address_mode": "ip",
                "transport": "tcp",
                "profile_variant": "ip_tcp",
                "profile_url": f"https://vpnobratno.info/servers/{hostname}/{hostname}_ip_tcp.ovpn",
            }
            for hostname in hostnames
        ]
        addresses = {
            hostname: f"8.8.8.{index}"
            for index, hostname in enumerate(hostnames, start=1)
        }

        def resolver(hostname, *_args):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addresses[hostname], 1194))]

        calls = []
        def fetcher(url, timeout, max_bytes):
            calls.append((url, max_bytes))
            if url == vpn_gate.VPNOBRATNO_LIST_URL:
                return b"<html>synthetic listing</html>"
            hostname = next(item["hostname"] for item in entries if item["profile_url"] == url)
            config = SAMPLE_CONFIG.replace(
                "remote old-volunteer-host.opengw.net 443",
                f"remote {addresses[hostname]} 1194",
            )
            return config.encode()

        with patch.object(vpn_gate, "parse_vpnobratno_listing", return_value=entries):
            servers, metadata = vpn_gate.discover_vpnobratno_servers(
                fetcher=fetcher, resolver=resolver, max_profiles=2
            )
        self.assertEqual(len(servers), 2)
        self.assertEqual(len(calls), 3)  # Listing plus two profile downloads.
        self.assertEqual(calls[0][1], vpn_gate.VPNOBRATNO_LISTING_MAX_BYTES)
        self.assertTrue(all(
            size == vpn_gate.VPNOBRATNO_PROFILE_MAX_BYTES for _, size in calls[1:]
        ))
        self.assertEqual(metadata["profile_links_found"], 4)
        self.assertEqual(metadata["profiles_considered_for_download"], 2)
        self.assertEqual(metadata["profiles_not_downloaded_due_to_limit"], 2)
        self.assertTrue(metadata["profile_download_limit_reached"])

    def test_discovery_stops_after_six_distinct_ip_profile_hosts_without_dns(self):
        hostnames = [f"vpn{100000001 + index}.opengw.net" for index in range(8)]
        entries = [
            {
                "hostname": hostname,
                "address_mode": "ip",
                "transport": "udp",
                "profile_variant": "ip_udp",
                "profile_url": f"https://vpnobratno.info/servers/{hostname}/{hostname}_ip_udp.ovpn",
            }
            for hostname in hostnames
        ]
        calls = []

        def fetcher(url, timeout, max_bytes):
            calls.append(url)
            if url == vpn_gate.VPNOBRATNO_LIST_URL:
                return b"<html>listing</html>"
            hostname = next(item["hostname"] for item in entries if item["profile_url"] == url)
            remote = f"8.8.8.{len(calls)}"
            return SAMPLE_CONFIG.replace(
                "proto tcp", "proto udp"
            ).replace(
                "remote old-volunteer-host.opengw.net 443", f"remote {remote} 1194"
            ).encode()

        def forbidden_resolver(*_args):
            raise AssertionError("IP profile discovery must not issue DNS lookups")

        with patch.object(vpn_gate, "parse_vpnobratno_listing", return_value=entries):
            servers, metadata = vpn_gate.discover_vpnobratno_servers(
                fetcher=fetcher,
                resolver=forbidden_resolver,
                max_profiles=24,
                max_unique_hosts=6,
            )

        self.assertEqual(len(servers), 6)
        self.assertEqual(len({server["hostname"] for server in servers}), 6)
        self.assertEqual(len(calls), 7)  # Listing plus six profile downloads.
        self.assertEqual(metadata["profiles_considered_for_download"], 6)
        self.assertEqual(metadata["unique_server_hostnames"], 6)
        self.assertEqual(metadata["discovery_stop_reason"], "distinct_server_host_budget_reached")
        self.assertFalse(metadata["profile_download_limit_reached"])

    def test_discovery_profile_download_limit_is_hard_capped(self):
        for value in (0, vpn_gate.VPNOBRATNO_PROFILE_DOWNLOAD_LIMIT + 1):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "max_profiles"):
                    vpn_gate.discover_vpnobratno_servers(
                        fetcher=lambda *_args, **_kwargs: b"",
                        max_profiles=value,
                    )

    def test_redirect_handler_accepts_same_https_origin_only(self):
        handler = vpn_gate.VPNObratnoSameOriginRedirect()
        request = urllib.request.Request(
            "https://vpnobratno.info/russia_server_list.html"
        )
        redirected = handler.redirect_request(
            request, None, 302, "Found", {},
            "https://vpnobratno.info/servers/example.ovpn",
        )
        self.assertEqual(
            redirected.full_url,
            "https://vpnobratno.info/servers/example.ovpn",
        )

    def test_fetcher_rejects_untrusted_input_before_opening_network(self):
        with patch.object(vpn_gate, "doh_query") as doh, patch.object(
            vpn_gate, "PinnedHTTPSConnection"
        ) as pinned:
            for url in (
                "http://vpnobratno.info/profile.ovpn",
                "https://evil.example/profile.ovpn",
                "https://vpnobratno.info.evil.example/profile.ovpn",
                "https://vpnobratno.info:8443/profile.ovpn",
            ):
                with self.subTest(url=url):
                    with self.assertRaisesRegex(vpn_gate.ProbeError, "trusted HTTPS origin"):
                        vpn_gate.fetch_vpnobratno_bytes(url)
            doh.assert_not_called()
            pinned.assert_not_called()

    def test_fetcher_uses_pinned_doh_and_enforces_response_size_during_read(self):
        class FakeSocket:
            def __init__(self):
                self.timeouts = []

            def settimeout(self, value):
                self.timeouts.append(value)

        class FakeResponse(io.BytesIO):
            status = 200

            def __init__(self, payload):
                super().__init__(payload)
                self.read_limits = []

            def getheader(self, name):
                return None

            def read1(self, size=-1):
                self.read_limits.append(size)
                return super().read(size)

        class FakeConnection:
            def __init__(self, response, host, address, port, timeout):
                self.response = response
                self.host = host
                self.address = address
                self.port = port
                self.timeout = timeout
                self.sock = FakeSocket()
                self.request_args = None
                self.closed = False

            def request(self, method, path, headers):
                self.request_args = (method, path, headers)

            def getresponse(self):
                self.timeout_set_before_response = bool(self.sock.timeouts)
                self.sock = None  # http.client transfers ownership to HTTPResponse
                return self.response

            def close(self):
                self.closed = True

        url = "https://vpnobratno.info/test"
        exact_response = FakeResponse(b"1234")
        exact_connections = []
        def exact_factory(host, address, port, timeout):
            item = FakeConnection(exact_response, host, address, port, timeout)
            exact_connections.append(item)
            return item

        with patch.object(vpn_gate, "doh_query", return_value=["8.8.8.8"]) as doh, patch.object(
            vpn_gate, "PinnedHTTPSConnection", side_effect=exact_factory
        ):
            self.assertEqual(vpn_gate.fetch_vpnobratno_bytes(url, timeout=12, max_bytes=4), b"1234")
        doh.assert_called_once_with("vpnobratno.info", "A", timeout=4)
        self.assertEqual(exact_response.read_limits[0], 5)
        self.assertEqual(len(exact_connections), 1)
        connection = exact_connections[0]
        self.assertEqual(
            (connection.host, connection.address, connection.port),
            ("vpnobratno.info", "8.8.8.8", 443),
        )
        self.assertEqual(connection.request_args[0:2], ("GET", "/test"))
        self.assertTrue(connection.closed)
        self.assertTrue(connection.timeout_set_before_response)
        self.assertIsNone(connection.sock)

        oversized_response = FakeResponse(b"12345")
        with patch.object(vpn_gate, "doh_query", return_value=["8.8.8.8"]), patch.object(
            vpn_gate, "PinnedHTTPSConnection",
            side_effect=lambda host, address, port, timeout: FakeConnection(
                oversized_response, host, address, port, timeout
            ),
        ):
            with self.assertRaisesRegex(
                vpn_gate.ProbeError, "exceeds configured 4-byte limit"
            ):
                vpn_gate.fetch_vpnobratno_bytes(url, timeout=12, max_bytes=4)
        self.assertEqual(oversized_response.read_limits[0], 5)

        with patch.object(vpn_gate, "doh_query") as doh:
            with self.assertRaisesRegex(ValueError, "max_bytes"):
                vpn_gate.fetch_vpnobratno_bytes(
                    url, max_bytes=vpn_gate.VPNOBRATNO_FETCH_HARD_MAX_BYTES + 1
                )
            doh.assert_not_called()

    def test_fetcher_follows_same_origin_redirect_but_rejects_cross_origin(self):
        class FakeSocket:
            def settimeout(self, _value):
                pass

        class FakeResponse(io.BytesIO):
            def __init__(self, status, payload=b"", location=None):
                super().__init__(payload)
                self.status = status
                self.location = location

            def getheader(self, name):
                return self.location if name.lower() == "location" else None

            def read1(self, size=-1):
                return super().read(size)

        class FakeConnection:
            def __init__(self, response, host, address, port, timeout):
                self.response = response
                self.sock = FakeSocket()
                self.host = host
                self.address = address
                self.port = port
                self.timeout = timeout
                self.path = None

            def request(self, method, path, headers):
                self.path = path

            def getresponse(self):
                return self.response

            def close(self):
                pass

        url = "https://vpnobratno.info/list"
        responses = [
            FakeResponse(302, location="/servers/profile.ovpn"),
            FakeResponse(200, b"profile"),
        ]
        connections = []
        def factory(host, address, port, timeout):
            item = FakeConnection(responses.pop(0), host, address, port, timeout)
            connections.append(item)
            return item

        with patch.object(vpn_gate, "doh_query", return_value=["8.8.8.8"]), patch.object(
            vpn_gate, "PinnedHTTPSConnection", side_effect=factory
        ):
            self.assertEqual(vpn_gate.fetch_vpnobratno_bytes(url), b"profile")
        self.assertEqual([item.path for item in connections], ["/list", "/servers/profile.ovpn"])

        bad_redirect = FakeResponse(302, location="https://evil.example/profile.ovpn")
        with patch.object(vpn_gate, "doh_query", return_value=["8.8.8.8"]), patch.object(
            vpn_gate, "PinnedHTTPSConnection",
            side_effect=lambda host, address, port, timeout: FakeConnection(
                bad_redirect, host, address, port, timeout
            ),
        ):
            with self.assertRaisesRegex(
                vpn_gate.ProbeError, "cross-origin or insecure redirect"
            ):
                vpn_gate.fetch_vpnobratno_bytes(url)

    def test_discovery_uses_the_same_origin_fetcher_by_default(self):
        defaults = vpn_gate.discover_vpnobratno_servers.__defaults__
        self.assertIs(defaults[0], vpn_gate.fetch_vpnobratno_bytes)



if __name__ == "__main__":
    unittest.main()
