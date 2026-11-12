import unittest
from audit_v41_p1_broad_clusters import cluster

def item(ip, source="kyoresuas-standard", cls="SHARED_INFRA"):
    return {"host": ip, "service_specificity_tier": "P1_BROAD_ONLY",
            "current_ip_lst": "YES", "origin_class": cls,
            "broad_24_or_wider_service_sources": source,
            "exact_32_service_sources": ""}

class BroadClusterTests(unittest.TestCase):
    def test_grouping_counts_only_exact_hosts(self):
        results, stats=cluster([
            item("192.0.2.1/32"),
            item("192.0.2.8/32",cls="OTHER"),
            item("192.0.3.1/32",source="w1zardz-service-direct")])
        self.assertEqual(stats["broad_only_current_hard_hosts"],3)
        group=next(r for r in results if r["group_prefix"]=="192.0.2.0/24")
        self.assertEqual(group["exact_conflict_hosts"],2)
        self.assertEqual(group["shared_hosts"],1)
        self.assertEqual(group["other_hosts"],1)
        self.assertEqual(group["scope"],"REVIEW_ONLY_NOT_A_BLOCKED_SUBNET")
        self.assertFalse(stats["automatic_subnet_carving"])

    def test_narrow_only_excluded(self):
        rows=[item("192.0.2.1/32"),item("192.0.2.2/32")]
        rows[1]["service_specificity_tier"]="P1_EXACT_ONLY"
        report,summary=cluster(rows)
        self.assertEqual(summary["broad_only_current_hard_hosts"],1)

    def test_duplicate_fails(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            cluster([item("192.0.2.1/32"),item("192.0.2.1/32")])

    def test_broad_only_with_exact_claim_fails(self):
        row=item("192.0.2.1/32")
        row["exact_32_service_sources"]="hxehex-mobile-hosts"
        with self.assertRaisesRegex(ValueError,"inconsistent"):
            cluster([row])

if __name__=="__main__":
    unittest.main()
