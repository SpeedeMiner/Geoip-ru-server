import unittest
from audit_v41_p1_service_specificity import triage


def row(host, cl="SHARED_INFRA", exact="", broad="", source="kyoresuas-standard"):
    return {
        "host":host,"origin_class":cl,
        "current_ip_lst":"YES",
        "review_priority":"P1_CURRENT_HARD_SHARED_OR_OTHER",
        "exact_32_service_sources":exact,
        "broad_24_or_wider_service_sources":broad,
        "service_evidence_present":"YES" if source else "NO"
    }


class P1ServiceSpecificityTests(unittest.TestCase):
    def test_exclusive_broad_exact_and_mixed(self):
        rows=[
            row("192.0.2.1/32",broad="kyoresuas-standard"),
            row("192.0.2.2/32",exact="hxehex-mobile-hosts",cl="OTHER"),
            row("192.0.2.3/32",exact="w1zardz-service-direct",broad="kyoresuas-standard"),
            row("192.0.2.4/32",source="")
        ]
        ordered, stats=triage(rows)
        self.assertEqual(stats["total_p1_current_ip_lst"],4)
        self.assertEqual(stats["service_specificity_counts"]["P1_BROAD_ONLY"],1)
        self.assertEqual(stats["service_specificity_counts"]["P1_EXACT_ONLY"],1)
        self.assertEqual(stats["service_specificity_counts"]["P1_BROAD_AND_EXACT"],1)
        self.assertEqual(stats["service_specificity_counts"]["P1_NO_SERVICE_CLAIM"],1)
        self.assertEqual([r["manual_review_order"] for r in ordered],["1","2","3","4"])
        self.assertTrue(all(r["routing_change_authorized"]=="NO" for r in ordered))

    def test_non_p1_ignored(self):
        r=row("192.0.2.5/32")
        r["review_priority"]="P2_CURRENT_HARD_CORE"
        rows,stats=triage([r])
        self.assertEqual(rows,[])
        self.assertEqual(stats["total_p1_current_ip_lst"],0)

    def test_duplicate_host_fails(self):
        with self.assertRaisesRegex(ValueError,"Invalid/duplicate"):
            triage([row("192.0.2.6/32"),row("192.0.2.6/32")])

    def test_invalid_p1_class_fails(self):
        with self.assertRaisesRegex(ValueError,"Inconsistent P1"):
            triage([row("192.0.2.7/32",cl="CORE_CORPORATE")])


if __name__=="__main__":
    unittest.main()
