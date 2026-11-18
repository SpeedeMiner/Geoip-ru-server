from __future__ import annotations

from contextlib import closing
import hashlib
import ipaddress
import json
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import MagicMock

import build_v41_overlay as overlay
from v41_release_manifest import CORE, SCHEMA, SNAPSHOT
from v41_vpn_exact_probe import bind_snapshot, load_exact_targets, measure_exact, public_ipv4

TARGET = {"id": "sample", "ip": "8.8.4.4", "prefix": "8.8.4.0/24", "domain": "test.example", "port": 443}


class Inputs(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "targets.json"
            p.write_text(data if isinstance(data, str) else json.dumps(data))
            return load_exact_targets(p)

    def test_allow_one_explicit_ipv4_with_optional_hostname(self):
        self.assertEqual(self.load([TARGET]), [TARGET])
        no_host = {k: v for k, v in TARGET.items() if k not in {"domain", "port"}}
        self.assertEqual(self.load([no_host])[0]["domain"], "")
        self.assertEqual(self.load([no_host])[0]["port"], 443)

    def test_limits_and_duplicate_json_keys(self):
        for raw in ([], [TARGET] * 7, " " * 8193, '[{"id":"a","id":"b","ip":"8.8.4.4","prefix":"8.8.4.0/24"}]'):
            with self.subTest(raw=repr(raw)[:50]), self.assertRaises(ValueError):
                self.load(raw)

    def test_bad_fields_and_special_addresses(self):
        for changes in ({"port": True}, {"port": 65536}, {"port": "443"}, {"prefix": "8.8.4.1/24"},
                        {"prefix": "0.0.0.0/0"}, {"prefix": "9.9.9.0/24"}, {"domain": "test.example\r\nFoo:x"},
                        {"extra": True}, {"ip": "2001:4860::1"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.load([{**TARGET, **changes}])
        for v in ("10.0.0.2", "127.0.0.1", "169.254.169.254", "192.0.0.9", "198.18.0.1", "224.0.0.1", "100.64.0.1"):
            with self.subTest(address=v), self.assertRaises(ValueError):
                public_ipv4(v)

    def test_pinned_manifest_matches_dat_and_contains_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = overlay.encode_geoip({"RU": {ipaddress.ip_network("8.8.4.0/24"), ipaddress.ip_network("2001:4860::/32")},
                                        "PRIVATE": {ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("fd00::/8")}})
            (root / "geoip_RU.dat").write_bytes(raw)
            sha = hashlib.sha256(raw).hexdigest()
            assets = {name: {"bytes": 1, "sha256": "0" * 64} for name in SNAPSHOT}
            assets["geoip_RU.dat"] = {"bytes": len(raw), "sha256": sha}
            for name in CORE[::2]:
                checksum = f"{assets[name]['sha256']}  {name}\n".encode()
                assets[name + ".sha256sum"] = {"bytes": len(checksum), "sha256": hashlib.sha256(checksum).hexdigest()}
                if name == "geoip_RU.dat":
                    (root / (name + ".sha256sum")).write_bytes(checksum)
            manifest = json.dumps({"schema": SCHEMA, "source_commit": "a" * 40, "assets": assets}).encode()
            (root / "geoip_RU_v41_release_manifest.json").write_bytes(manifest)
            pin = hashlib.sha256(manifest).hexdigest()
            result, rows = bind_snapshot(root, "b" * 40, pin, [TARGET])
            self.assertEqual(rows, [{"id": "sample", "geoip_category": "RU"}])
            self.assertEqual(result["dat_sha256"], sha)
            with self.assertRaises(ValueError):
                bind_snapshot(root, "b" * 40, "0" * 64, [TARGET])
            (root / "geoip_RU.dat.sha256sum").write_text("0" * 64 + "  geoip_RU.dat\n")
            with self.assertRaises(ValueError):
                bind_snapshot(root, "b" * 40, pin, [TARGET])


class Observations(unittest.TestCase):
    def test_tcp_timeout_is_not_tls_or_http_result(self):
        fail = MagicMock(side_effect=TimeoutError)
        row = measure_exact(TARGET, 1, resolver=lambda *_: ([], []), connect=fail)
        self.assertEqual((row["tcp"], row["tls"], row["http"]), ("TCP_TIMEOUT", "NOT_TESTED", "NOT_TESTED"))

    def test_failed_dial_and_bad_tls_are_different(self):
        row = measure_exact(TARGET, 1, resolver=lambda *_: ([], []),
                            connect=MagicMock(side_effect=ConnectionRefusedError))
        self.assertEqual((row["tcp"], row["tls"]), ("PROBE_ERROR", "NOT_TESTED"))
        sock, ctx = MagicMock(), MagicMock()
        ctx.wrap_socket.side_effect = ssl.SSLCertVerificationError
        row = measure_exact(TARGET, 1, resolver=lambda *_: ([], []), connect=lambda *a, **k: sock, context=lambda: ctx)
        self.assertEqual((row["tcp"], row["tls"], row["http"]), ("TCP_OK", "PROBE_ERROR", "NOT_TESTED"))
        sock.close.assert_called_once()

    def test_http_response_is_transport_evidence_and_dns_mismatch_is_independent(self):
        sock, tls, ctx = MagicMock(), MagicMock(), MagicMock()
        ctx.wrap_socket.return_value = tls
        reply = MagicMock()
        reply.status = 403
        row = measure_exact(TARGET, 1, resolver=lambda *_: (["9.9.9.9"], ["2606:4700:4700::1111"]),
                            connect=lambda *a, **k: sock, context=lambda: ctx,
                            response=lambda *a, **k: closing(reply))
        self.assertEqual((row["tcp"], row["tls"], row["http"], row["http_status"]), ("TCP_OK", "TLS_OK", "HTTP_OK", 403))
        self.assertFalse(row["dns_matches_target"])
        self.assertEqual(row["ipv6_transport"], "NOT_TESTED")
        ctx.wrap_socket.assert_called_once_with(sock, server_hostname=TARGET["domain"])
        tls.close.assert_called_once()

    def test_tcp_only_does_not_resolve_or_open_tls(self):
        dns = MagicMock()
        row = measure_exact({**TARGET, "domain": ""}, 1, resolver=dns, connect=lambda *a, **k: MagicMock())
        self.assertEqual((row["dns"], row["tcp"], row["tls"], row["http"]),
                         ("NOT_TESTED", "TCP_OK", "NOT_TESTED", "NOT_TESTED"))
        dns.assert_not_called()
