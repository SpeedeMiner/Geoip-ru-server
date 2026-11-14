import socket
from types import SimpleNamespace
import unittest

import replay_v41_citic_xray as replay


class CiticXrayReplayTests(unittest.TestCase):
    def test_socks_literals_and_hostname_roundtrip(self):
        sender, receiver = socket.socketpair()
        with sender, receiver:
            for name in ("192.0.2.3", "2001:db8::3", "example.test"):
                sender.sendall(replay.write_host(name))
                self.assertEqual(replay.read_host(receiver, replay.recv(receiver, 1)[0]), name)

    def test_config_has_no_path_to_dial_an_audited_destination(self):
        sinks = [
            SimpleNamespace(route="PROXY", server_address=("127.0.0.1", 49151)),
            SimpleNamespace(route="DIRECT", server_address=("127.0.0.1", 49152)),
        ]
        for strategy in (None, *replay.STRATEGIES):
            with self.subTest(strategy=strategy):
                cfg = replay.build_config(49153, sinks, 49154, strategy)
                self.assertEqual(cfg["inbounds"][0]["listen"], "127.0.0.1")
                self.assertEqual(cfg["outbounds"][0]["tag"], "PROXY")
                self.assertEqual([x["protocol"] for x in cfg["outbounds"][:2]], ["socks", "socks"])
                self.assertTrue(all(
                    x["settings"]["servers"][0]["address"] == "127.0.0.1"
                    for x in cfg["outbounds"][:2]
                ))
                routing = cfg["routing"]
                if strategy is None:
                    self.assertNotIn("dns", cfg)
                    self.assertEqual(routing["domainStrategy"], "AsIs")
                    self.assertEqual(len(cfg["outbounds"]), 2)
                else:
                    self.assertEqual(cfg["dns"]["servers"], [{"address": "127.0.0.1", "port": 49154}])
                    self.assertEqual(cfg["dns"]["queryStrategy"], strategy)
                    self.assertEqual(routing["domainStrategy"], "IPOnDemand")
                    self.assertEqual(routing["rules"][:2], [
                        {"type": "field", "inboundTag": ["fixture-dns"], "ip": ["127.0.0.1/32"],
                         "port": 49154, "outboundTag": "loopback-dns"},
                        {"type": "field", "inboundTag": ["fixture-dns"], "outboundTag": "deny-dns"},
                    ])

    def test_committed_case_data_keeps_scope_and_negative_control(self):
        as_is = replay.fixture("v41-citic-xray-route-delta-20261114.json")
        dns = replay.fixture("v41-citic-xray-dns-strategies-20261114.json")
        targets = as_is["targets"]
        changed = {host for host, x in targets.items() if x["fixed_observed"] != x["shadow_observed"]}
        self.assertEqual(len(targets), 71)
        self.assertEqual(changed, {host for host, x in targets.items() if x["category"] == "exact_ru_ipv6"})
        self.assertEqual(len(changed), 10)
        self.assertEqual(len(dns["targets"]), 11)
        self.assertEqual(dns["route_changes_by_dns_strategy"], {"UseIPv4": 0, "UseIPv6": 10, "UseIP": 0})
        dual = replay.fixture("v41-citic-loopback-dns-20261114.json")
        kz = dual["2001:ad0:cff::81"]["name"].lower().rstrip(".")
        for mode in replay.STRATEGIES:
            self.assertEqual(dns["targets"][kz][mode]["fixed"]["route"], "PROXY")
            self.assertEqual(dns["targets"][kz][mode]["shadow"]["route"], "PROXY")

    def test_explicit_final_rule_stays_in_socks_fixture(self):
        doc = replay.fixture("v41-citic-xray-final-rule-20261114.json")
        sinks = [
            SimpleNamespace(route="PROXY", server_address=("127.0.0.1", 49151)),
            SimpleNamespace(route="DIRECT", server_address=("127.0.0.1", 49152)),
        ]
        self.assertEqual(doc["cases"], 66)
        for name, scenario in doc["scenarios"].items():
            with self.subTest(name=name):
                cfg = replay.build_order_config(49153, sinks, 49154, scenario)
                rules = cfg["routing"]["rules"]
                self.assertEqual(cfg["dns"]["queryStrategy"], "UseIPv6")
                self.assertEqual(cfg["routing"]["domainStrategy"], scenario["domainStrategy"])
                self.assertEqual(cfg["outbounds"][0]["protocol"], "socks")
                if scenario["terminal_proxy_rule"]:
                    self.assertEqual(rules[-1], {
                        "type": "field", "network": "tcp,udp", "outboundTag": "PROXY",
                    })
                else:
                    self.assertEqual(rules[-1]["outboundTag"], "DIRECT")
                expected = 0 if name == "ip_if_non_match_terminal_proxy" else 10
                self.assertEqual(len(scenario["changes"]), expected)
