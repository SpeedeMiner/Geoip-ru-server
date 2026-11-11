import base64
import csv
import io
import json
import urllib.error
import urllib.request
import pathlib
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import vpn_gate


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

    def test_server_selection_prefers_distinct_origin_asns(self):
        servers = [
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 100},
            {"hostname": "b", "server_ip": "8.8.8.2", "score": 90},
            {"hostname": "c", "server_ip": "8.8.8.3", "score": 80},
            {"hostname": "d", "server_ip": "8.8.8.4", "score": 70},
        ]
        asns = {"8.8.8.1": 12345, "8.8.8.2": 12345, "8.8.8.3": 54321, "8.8.8.4": 65001}
        with patch.object(vpn_gate, "network_info", side_effect=lambda ip: {"asn": asns[ip], "prefix": ""}):
            selected, metadata = vpn_gate.select_diverse_servers(servers, 3)
        self.assertEqual([server["hostname"] for server in selected], ["a", "c", "d"])
        self.assertEqual(metadata["selected_distinct_asns"], 3)
        self.assertEqual(metadata["selected_asns"], [12345, 54321, 65001])

    def test_server_selection_fills_budget_after_each_asn_has_a_chance(self):
        servers = [
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 100},
            {"hostname": "b", "server_ip": "8.8.8.2", "score": 90},
            {"hostname": "c", "server_ip": "8.8.8.3", "score": 80},
        ]
        asns = {"8.8.8.1": 12345, "8.8.8.2": 12345, "8.8.8.3": 65001}
        with patch.object(vpn_gate, "network_info", side_effect=lambda ip: {"asn": asns[ip], "prefix": ""}):
            selected, metadata = vpn_gate.select_diverse_servers(servers, 3)
        self.assertEqual([server["hostname"] for server in selected], ["a", "c", "b"])
        self.assertEqual(metadata["selected_distinct_asns"], 2)


    def test_one_successful_exit_allows_three_distinct_asn_fallback_attempts(self):
        servers = [
            {"hostname": "a", "server_ip": "8.8.8.1", "score": 100},
            {"hostname": "b", "server_ip": "8.8.8.2", "score": 90},
            {"hostname": "c", "server_ip": "8.8.8.3", "score": 80},
            {"hostname": "d", "server_ip": "8.8.8.4", "score": 70},
        ]
        asns = {"8.8.8.1": 12345, "8.8.8.2": 12345, "8.8.8.3": 54321, "8.8.8.4": 65001}
        with patch.object(vpn_gate, "network_info", side_effect=lambda ip: {"asn": asns[ip], "prefix": ""}):
            selected, metadata = vpn_gate.select_diverse_servers(
                servers, max_servers=1, max_attempts=3
            )
        self.assertEqual([server["hostname"] for server in selected], ["a", "c", "d"])
        self.assertEqual(metadata["selected_distinct_asns"], 3)
        self.assertEqual(metadata["max_connection_attempts"], 3)

    def test_max_attempts_cannot_be_lower_than_successful_exit_target(self):
        with self.assertRaisesRegex(ValueError, "max_attempts"):
            vpn_gate.select_diverse_servers([], max_servers=2, max_attempts=1)

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
    def test_no_verified_ru_exit_is_not_a_successful_measurement(self):
        self.assertNotEqual(vpn_gate.measurement_exit_code(0, 1), 0)
        self.assertEqual(vpn_gate.measurement_exit_code(1, 1), 0)
        self.assertEqual(vpn_gate.measurement_exit_code(2, 1), 0)


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


class VPNGateDoHTests(unittest.TestCase):
    def test_doh_query_uses_pinned_resolver_and_filters_requested_type(self):
        class FakeResponse:
            status = 200
            def read(self, limit):
                return json.dumps({
                    "Status": 0,
                    "Answer": [
                        {"type": 1, "data": "8.8.8.8"},
                        {"type": 28, "data": "2001:4860:4860::8888"},
                        {"type": 1, "data": "10.0.0.1"},
                    ],
                }).encode()

        class FakeConnection:
            def __init__(self, host, address, timeout):
                self.host, self.address, self.timeout = host, address, timeout
                self.request_args = None
            def request(self, method, path, headers):
                self.request_args = (method, path, headers)
            def getresponse(self):
                return FakeResponse()
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
        profiles = vpn_gate.parse_vpnobratno_listing(self.listing(links))
        self.assertEqual(
            [item["profile_variant"] for item in profiles],
            ["ip_udp", "ddns_udp"],
        )
        self.assertTrue(all(
            item["profile_url"].startswith("https://vpnobratno.info/servers/")
            for item in profiles
        ))

    def test_ddns_remote_must_match_the_hostname_from_listing(self):
        address = vpn_gate.resolve_vpnobratno_server_ip(
            self.HOST, self.HOST, "ddns", self.resolver
        )
        self.assertEqual(address, "8.8.8.8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            vpn_gate.resolve_vpnobratno_server_ip(
                self.HOST, "attacker.example", "ddns", self.resolver
            )

    def test_ip_variant_must_match_public_dns_address_of_listed_host(self):
        address = vpn_gate.resolve_vpnobratno_server_ip(
            self.HOST, "8.8.8.8", "ip", self.resolver
        )
        self.assertEqual(address, "8.8.8.8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            vpn_gate.resolve_vpnobratno_server_ip(
                self.HOST, "1.1.1.1", "ip", self.resolver
            )

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

        def fetcher(url, timeout):
            calls.append((url, timeout))
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

        def fetcher(url, timeout):
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


class VPNObratnoFetchSafetyTests(unittest.TestCase):
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

    def test_discovery_uses_the_same_origin_fetcher_by_default(self):
        defaults = vpn_gate.discover_vpnobratno_servers.__defaults__
        self.assertIs(defaults[0], vpn_gate.fetch_vpnobratno_bytes)



if __name__ == "__main__":
    unittest.main()
