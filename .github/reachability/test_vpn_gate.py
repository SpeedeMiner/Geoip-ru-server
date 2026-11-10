import base64
import csv
import io
import pathlib
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


class OpenVPNProfileSafetyTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
