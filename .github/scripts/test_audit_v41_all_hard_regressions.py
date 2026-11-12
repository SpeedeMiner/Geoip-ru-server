import hashlib
import unittest

from audit_v41_all_hard_regressions import compare


def fixture():
    files = {
        "CORE_CORPORATE": b"192.0.2.1/32\n",
        "SHARED_INFRA": b"198.51.100.1/32\n",
        "OTHER": b"203.0.113.1/32\n",
    }
    counts = {"CORE_CORPORATE": 1, "SHARED_INFRA": 1, "OTHER": 1}
    baseline = {"schema": 1, "observation_only_not_approved": True,
                "categories": {name: {
                    "ipv4_addresses": counts[name],
                    "current_ip_lst_addresses": counts[name],
                    "cidr_list_sha256": hashlib.sha256(payload).hexdigest(),
                } for name, payload in files.items()}}
    summary = {"by_family":{"ipv4":{"by_origin_class": {
        key: {"addresses": 1, "current_antifilter_ip_addresses": 1}
        for key in files}}}}
    return baseline, summary, files


class AllHardRegressionTests(unittest.TestCase):
    def test_unmodified_snapshot(self):
        baseline, summary, files = fixture()
        result=compare(baseline,summary,files)
        self.assertEqual(result["number_of_observation_changes"],0)
        self.assertFalse(result["baseline_is_approval"])

    def test_same_count_different_address_flags_regression(self):
        baseline, summary, files = fixture()
        files["SHARED_INFRA"]=b"198.51.100.2/32\n"
        result=compare(baseline,summary,files)
        self.assertEqual(result["number_of_observation_changes"],1)
        self.assertEqual(result["observation_changes"][0]["type"],"CIDR_SET_CHANGED")

    def test_current_hard_growth_warns(self):
        baseline, summary, files = fixture()
        summary["by_family"]["ipv4"]["by_origin_class"]["OTHER"]["current_antifilter_ip_addresses"]=2
        result=compare(baseline,summary,files)
        self.assertEqual(result["number_of_observation_changes"],1)
        self.assertEqual(result["observation_changes"][0]["delta"],1)

    def test_observation_baseline_cannot_be_approval(self):
        baseline, summary, files = fixture()
        baseline["observation_only_not_approved"]=False
        with self.assertRaisesRegex(ValueError,"Unverified"):
            compare(baseline,summary,files)


if __name__=="__main__":
    unittest.main()
