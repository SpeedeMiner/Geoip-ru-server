import unittest

from audit_v41_service_coverage import compare, family_report

PROJ = {"rules": [{"match": "BLOCK", "outbound": "BLOCK"}, {"match": "RU", "outbound": "DIRECT"},
                  {"match": "GEOIP_RU", "outbound": "DIRECT"}], "default": "PROXY"}


def observation(answers):
    return {"time_utc": "2026-11-15T14:04:37+00:00", "resolver": "fixture", "status": 0, "answers": answers}


class ServiceCoverageTests(unittest.TestCase):
    def test_shared_ipv4_observation_does_not_expand_geoip(self):
        sample = observation([{"type": 1, "data": "192.0.2.1"}, {"type": 1, "data": "192.0.2.2"},
                              {"type": 5, "data": "proxy.example."}])
        mask = ((3221225985, 3221225985),)
        result = family_report([sample], mask, PROJ, {"RU": "exact"}, 4)
        self.assertEqual(result["geoip"], "PARTIAL_DIRECT")
        self.assertEqual(result["addresses"]["192.0.2.2"], {"geoip_direct": False, "profile_simulation": "DIRECT"})
        self.assertEqual(result["cnames"], ["proxy.example"])
        self.assertEqual(mask, ((3221225985, 3221225985),))

    def test_rule_order_and_no_profile(self):
        sample = observation([{"type": 28, "data": "2001:db8::1"}])
        categories = {"RU": "exact", "BLOCK": "exact"}
        def result(profile):
            return family_report([sample], [], profile, categories, 6)["addresses"]["2001:db8::1"]
        self.assertEqual(result(PROJ)["profile_simulation"], "BLOCK")
        self.assertEqual(result({**PROJ, "rules": list(reversed(PROJ["rules"]))})["profile_simulation"], "DIRECT")
        self.assertIsNone(result(None)["profile_simulation"])

    def test_missing_dns_and_no_address_are_not_a_negative_match(self):
        self.assertEqual(family_report([], [], PROJ, None, 6)["geoip"], "NO_DNS_OBSERVATION")
        self.assertEqual(family_report([observation([])], [], None, {}, 6)["geoip"], "NO_ADDRESS_OBSERVED")
        self.assertIsNone(family_report([observation([])], [], PROJ, None, 6)["profile_simulation_without_address"])
        row, = compare({"example.test": {"domain": "example.test"}}, {"domains": [], "dns": []}, {4: [], 6: []})
        self.assertIsNone(row["geosite_observed_matches"])
        self.assertEqual(row["actual_client_route"], "UNKNOWN")
