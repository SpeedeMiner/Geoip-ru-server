from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import v41_vpn_gate as gate
from v41_vpn_exact_probe import observation

IDENTITY = {"ipv4": "84.17.50.24", "asn": 12714, "country": "RU", "https_status": 200, "agreeing_sources": 2}
TARGET = {"id": "test", "ip": "8.8.4.4", "port": 443, "domain": "test.example", "prefix": "8.8.4.0/24"}
PROFILE = """client
remote 84.17.50.24 1194
proto udp
up /tmp/never-run
plugin /tmp/not-a-plugin
<ca>
MAA=
invalid
</ca>
""".replace("MAA=\ninvalid", "-----BEGIN CERTIFICATE-----\nMAA=\n-----END CERTIFICATE-----")


class Preparation(unittest.TestCase):
    def test_only_reviewed_profile_material_is_used(self):
        addr, port, proto, cfg = gate.parse_profile(PROFILE, mode="ip")
        self.assertEqual((addr, port, proto), ("84.17.50.24", 1194, "udp"))
        self.assertIn("remote-cert-tls server", cfg)
        self.assertNotIn("never-run", cfg)
        self.assertNotIn("not-a-plugin", cfg)
        with self.assertRaises(ValueError):
            gate.parse_profile(PROFILE + "tls-auth /tmp/key\n", mode="ip")
        with self.assertRaises(ValueError):
            gate.parse_profile(PROFILE.replace("84.17.50.24", "169.254.169.254"), mode="ip")
        with self.assertRaises(ValueError):
            gate.parse_profile(PROFILE, mode="ip", transport="tcp")
        with self.assertRaises(ValueError):
            gate.parse_profile(PROFILE.replace("MAA=", "up /tmp/inject"), mode="ip")

    def test_same_origin_links_only(self):
        path = "/servers/vpn12.opengw.net/vpn12.opengw.net_ip_udp.ovpn"
        x = gate.profile_links(f'<a href="{path}">ok</a><a href="https://other.example{path}">no</a>'
                               f'<a href="https://vpnobratno.info{path}?query=1">no</a>')
        self.assertEqual(len(x), 1)
        self.assertEqual(x[0][:3], ("vpn12.opengw.net", "ip", "udp"))

    def test_prepared_ddns_address_requires_no_resolver_in_the_namespace(self):
        hostname = "vpn12.opengw.net"
        profile = PROFILE.replace("84.17.50.24", hostname)
        with patch.object(gate.socket, "getaddrinfo", side_effect=AssertionError("unexpected DNS")):
            address, _, _, config = gate.parse_profile(profile, hostname=hostname, mode="ddns",
                                                       resolved_ddns="84.17.50.24")
        self.assertEqual(address, "84.17.50.24")
        self.assertIn("disable-dco\nmark 65", config)

    def test_logs_do_not_export_addresses_paths_profiles_or_keys(self):
        raw = b"AUTH_FAILED user=unsafe IP=84.17.50.24\nVERIFY ERROR /secret.pkcs12\n-----BEGIN SECRET-----"
        self.assertEqual(gate.sanitize_openvpn(raw), ["AUTH_REJECTED", "CERTIFICATE_REJECTED"])


class Controls(unittest.TestCase):
    def test_https_200_and_independent_ru_ip_asn_votes(self):
        response = json.dumps({"ip": IDENTITY["ipv4"], "country": "RU", "org": "AS12714 Example"}).encode()
        transfer = MagicMock(side_effect=[response, response, b""])
        self.assertEqual(gate.verify_exit(transfer=transfer), IDENTITY)
        self.assertEqual(transfer.call_args.kwargs, {"cap": 0, "method": "HEAD"})

    def test_divergent_asn_and_failed_control_are_fail_closed(self):
        first = {"ip": IDENTITY["ipv4"], "country_code": "RU", "asn": 12714}
        second = {**first, "asn": 8359}
        data = lambda p: json.dumps(p).encode()
        with self.assertRaises(gate.ProbeError):
            gate.verify_exit(transfer=MagicMock(side_effect=[data(first), data(second), TimeoutError()]))
        with self.assertRaises(gate.ProbeError):
            gate.verify_exit(transfer=MagicMock(side_effect=[data(first), data(first), gate.ProbeError("non-200")]))

    def test_third_provider_breaks_disagreement(self):
        first = {"ip": IDENTITY["ipv4"], "country_code": "RU", "asn": 12714}
        second = {**first, "asn": 8359}
        data = lambda p: json.dumps(p).encode()
        transfer = MagicMock(side_effect=[data(first), data(second), data(first), b""])
        self.assertEqual(gate.verify_exit(transfer=transfer), IDENTITY)
        self.assertEqual(transfer.call_count, 4)

    def series(self, after):
        report = {"status": "NOT_TESTED", "targets": [observation(TARGET)]}
        history = []
        kwargs = dict(control=MagicMock(side_effect=[IDENTITY, after]), measure=MagicMock(return_value={**TARGET, "tcp": "TCP_OK"}),
                      via_tun=lambda *_: True, save=lambda row: history.append(copy.deepcopy(row)))
        verified = gate.run_series([TARGET], report, **kwargs)
        return verified, report, history

    def test_postflight_must_match_the_same_ip_and_asn(self):
        for change in ({"ipv4": "88.210.36.192"}, {"asn": 8359}, {"country": "KZ"}, {"https_status": 403}):
            with self.subTest(change=change):
                verified, report, history = self.series({**IDENTITY, **change})
                self.assertFalse(verified)
                self.assertEqual(report["status"], "POSTFLIGHT_INCONCLUSIVE")
                self.assertEqual(history[0]["targets"][0]["tcp"], "NOT_TESTED")
        self.assertFalse(self.series(TimeoutError())[0])
        self.assertTrue(self.series(IDENTITY)[0])

    def test_no_target_before_good_preflight(self):
        report = {"status": "NOT_TESTED", "targets": [observation(TARGET)]}
        probe = MagicMock()
        with self.assertRaises(gate.ProbeError):
            gate.run_series([TARGET], report, control=MagicMock(side_effect=gate.ProbeError("no exit")),
                            measure=probe, save=MagicMock())
        probe.assert_not_called()
        self.assertEqual(report["targets"][0]["tcp"], "NOT_TESTED")

    def test_route_to_relay_outside_tunnel_never_gets_measured(self):
        report = {"targets": [observation(TARGET)]}
        probe = MagicMock()
        gate.run_series([TARGET], report, control=MagicMock(return_value=IDENTITY), measure=probe,
                        save=MagicMock(), via_tun=lambda *_: False)
        probe.assert_not_called()
        self.assertEqual(report["targets"][0]["errors"]["tcp"], "ROUTE_NOT_TUNNEL")


class Isolation(unittest.TestCase):
    def test_firewall_rolls_back_partial_setup_and_measurement_failure(self):
        for fail_setup in (False, True):
            events = []

            def run(name, *args, data=None):
                events.append((name, args, data))
                if name.endswith("-save"):
                    return name.encode()
                if fail_setup and name == "iptables-restore" and b"tap0" in data:
                    raise subprocess.CalledProcessError(1, name)

            with self.assertRaises((TimeoutError, subprocess.CalledProcessError)):
                with gate.firewall("84.17.50.24", 1194, "udp", run=run):
                    raise TimeoutError
            self.assertEqual(events[-2:], [("iptables-restore", (), b"iptables-save"),
                                          ("ip6tables-restore", (), b"ip6tables-save")])
            self.assertIn(b":OUTPUT DROP", events[2][2])
            self.assertIn(b"-o tap0 -d 84.17.50.24", events[3][2])
            self.assertIn(b"-m mark --mark 65", events[3][2])

    def test_restore_failure_aborts_the_namespace(self):
        def run(name, *args, data=None):
            if name.endswith("-save"):
                return b"before"
            if data == b"before":
                raise subprocess.CalledProcessError(1, name)
        with self.assertRaises(gate.AbortRun):
            with gate.firewall("84.17.50.24", 1194, "udp", run=run):
                pass

    def test_wrapper_cleanup_on_success_probe_failure_and_slirp_failure(self):
        script = Path(__file__).with_name("v41_vpn_netns_exec.sh").read_text()
        for case, expected in (("success", 0), ("probe", 42), ("slirp", 2)):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                run = root / "run"
                run.mkdir()
                (run / "netns").mkdir()
                etc = root / "etc"
                (etc / "netns").mkdir(parents=True)
                mocks = root / "bin"
                mocks.mkdir()
                wrapped = root / "netns.sh"
                wrapped.write_text(script.replace("/etc/netns/", str(etc / "netns") + "/")
                                   .replace("/run/", str(run) + "/"))
                for name, data in {
                    "id": 'echo 0',
                    "ip": '''
                        printf '%s\\n' "$*" >> "$MOCK_LOG"
                        case "$2" in
                          add) touch "$MOCK_RUN/netns/$3";;
                          pids) :;;
                          exec) test "$MOCK_CASE" != probe || exit 42;;
                          del) rm -- "$MOCK_RUN/netns/$3";;
                          *) exit 9;;
                        esac
                    ''',
                    "slirp4netns": '''
                        if [ "$MOCK_CASE" = slirp ]; then printf 0 >&3; else printf 1 >&3; fi
                        exec cat >/dev/null
                    ''',
                }.items():
                    mock = mocks / name
                    mock.write_text("#!/bin/bash\n" + data + "\n")
                    mock.chmod(0o755)
                log = root / "mock.log"
                env = {**os.environ, "PATH": str(mocks) + ":" + os.environ["PATH"], "MOCK_RUN": str(run),
                       "MOCK_CASE": case, "MOCK_LOG": str(log)}
                result = subprocess.run(["bash", str(wrapped), "--", "test-probe"], env=env,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertFalse(list((etc / "netns").iterdir()))
                self.assertFalse(list((run / "netns").iterdir()))
                self.assertEqual(sorted(p.name for p in run.iterdir()), ["netns"])
                self.assertIn("netns del", log.read_text())
                self.assertNotRegex("\n".join(l for l in script.splitlines() if not l.lstrip().startswith("#")), r"\b(sysctl|iptables|ip link)\s")
