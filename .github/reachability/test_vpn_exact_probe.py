import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import vpn_exact_probe as probe


class ExactProbeTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "targets.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return probe.load_exact_targets(path)

    def test_only_explicit_public_ipv4_endpoints_are_accepted(self):
        item = {"id": "one", "ip": "1.1.1.1", "prefix": "1.1.1.0/24", "domain": "example.com"}
        self.assertEqual(self.load([item])[0]["port"], 443)
        for bad in ([], [item] * 7, [item, item], [{**item, "ip": "127.0.0.1"}],
                    [{**item, "ip": "1.1.2.1"}], [{**item, "prefix": "1.1.1.1/24"}],
                    [{**item, "domain": "example.com\r\nInjected: x"}],
                    [{**item, "port": True}], [{**item, "unknown": "x"}],
                    [{**item, "ip": "2606:4700:4700::1111", "prefix": "2606:4700:4700::/48"}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.load(bad)

    @patch("vpn_exact_probe.socket.create_connection")
    def test_tcp_only_does_not_resolve_or_send_http(self, connect):
        sock = Mock(); connect.return_value = sock
        resolver = Mock(side_effect=AssertionError("DNS not requested"))
        target = {"id": "one", "ip": "1.1.1.1", "prefix": "1.1.1.0/24", "domain": "", "port": 443}
        row = probe.measure_exact(target, {"ip": "1.2.3.4", "country": "RU", "asn": 1, "org": ""}, 3, resolver, "now")
        connect.assert_called_once_with(("1.1.1.1", 443), timeout=3)
        self.assertEqual((row["TCP_RESULT"], row["TLS_RESULT"], row["HTTPS_RESULT"]), ("CONNECTED", "NOT_TESTED", "NOT_TESTED"))
        self.assertEqual(row["IPV6_TRANSPORT"], "NOT_TESTED_TUNNEL_IPV4_ONLY")
        sock.sendall.assert_not_called(); sock.close.assert_called_once()

    @patch("vpn_exact_probe.socket.create_connection", side_effect=TimeoutError("timeout"))
    def test_timeout_is_inconclusive_not_blocked(self, connect):
        target = {"id": "one", "ip": "1.1.1.1", "prefix": "1.1.1.0/24", "domain": "", "port": 443}
        row = probe.measure_exact(target, {"ip": "1.2.3.4", "country": "RU", "asn": 1, "org": ""}, 3, Mock(), "now")
        self.assertEqual(row["TCP_RESULT"], "INCONCLUSIVE")
        self.assertEqual(row["TLS_RESULT"], "NOT_TESTED")

    @patch("vpn_exact_probe.socket.create_connection")
    def test_non_ru_exit_never_contacts_endpoint(self, connect):
        target = {"id": "one", "ip": "1.1.1.1", "prefix": "1.1.1.0/24", "domain": "", "port": 443}
        with self.assertRaisesRegex(ValueError, "verified RU"):
            probe.measure_exact(target, {"ip": "1.2.3.4", "country": "NL", "asn": 1, "org": ""}, 3, Mock(), "now")
        connect.assert_not_called()

    @patch("vpn_exact_probe.ssl.create_default_context")
    @patch("vpn_exact_probe.socket.create_connection")
    def test_dns_mismatch_and_certificate_failure_are_separate(self, connect, context):
        connect.return_value = Mock()
        context.return_value.wrap_socket.side_effect = probe.ssl.SSLCertVerificationError("bad certificate")
        resolver = Mock(return_value=(("DNS_ANSWER", ["1.1.1.2"], ""), ("DNS_NO_ANSWER", [], "")))
        target = {"id": "one", "ip": "1.1.1.1", "prefix": "1.1.1.0/24", "domain": "example.com", "port": 443}
        row = probe.measure_exact(target, {"ip": "1.2.3.4", "country": "RU", "asn": 1, "org": ""}, 3, resolver, "now")
        self.assertFalse(row["DNS_MATCHES_TARGET"])
        self.assertEqual(row["TCP_RESULT"], "CONNECTED")
        self.assertEqual(row["TLS_RESULT"], "INCONCLUSIVE")
        self.assertEqual(row["HTTPS_RESULT"], "NOT_TESTED")
        self.assertEqual(context.return_value.wrap_socket.call_args.kwargs["server_hostname"], "example.com")

    @patch("vpn_exact_probe.http.client.HTTPResponse")
    @patch("vpn_exact_probe.ssl.create_default_context")
    @patch("vpn_exact_probe.socket.create_connection")
    def test_https_response_keeps_exact_address_and_host(self, connect, context, response):
        raw, tls = Mock(), Mock()
        connect.return_value = raw; context.return_value.wrap_socket.return_value = tls
        response.return_value.status = 403
        resolver = Mock(return_value=(("DNS_ANSWER", ["1.1.1.1"], ""), ("DNS_NO_ANSWER", [], "")))
        target = {"id": "one", "ip": "1.1.1.1", "prefix": "1.1.1.0/24", "domain": "example.com", "port": 443}
        row = probe.measure_exact(target, {"ip": "1.2.3.4", "country": "RU", "asn": 1, "org": ""}, 3, resolver, "now")
        self.assertEqual((row["TCP_RESULT"], row["TLS_RESULT"], row["HTTPS_RESULT"], row["HTTP_STATUS"]),
                         ("CONNECTED", "VERIFIED", "HTTP_RESPONSE", 403))
        self.assertTrue(row["DNS_MATCHES_TARGET"])
        self.assertIn(b"Host: example.com\r\n", tls.sendall.call_args.args[0])
        tls.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
