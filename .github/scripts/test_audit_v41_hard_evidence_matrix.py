import ipaddress
import tempfile
import unittest
from pathlib import Path
from audit_v41_hard_evidence_matrix import read_ip_hosts, build_matrix, summary


def nets(*entries):
    return {ipaddress.ip_network(x) for x in entries}

class EvidenceMatrixTests(unittest.TestCase):
    def test_classification_and_evidence_priority(self):
        groups={
            "CORE_CORPORATE": {ipaddress.ip_address("192.0.2.1")},
            "SHARED_INFRA": {ipaddress.ip_address("198.51.100.2")},
            "OTHER": {ipaddress.ip_address("203.0.113.3")}
        }
        hard=[
            (ipaddress.ip_network("192.0.2.1/32"),{"antifilter-ip.lst"}),
            (ipaddress.ip_network("198.51.100.0/30"),{"antifilter-ip.lst","v38-baseline-hard-or-unclassified"}),
            (ipaddress.ip_network("203.0.113.3/32"),{"v38-baseline-hard-or-unclassified"})
        ]
        rows=build_matrix(groups,hard,{"kyoresuas-standard":nets("198.51.100.0/24"),
                                      "hxehex-mobile-hosts":nets("203.0.113.3/32")},
            core=nets("192.0.2.0/24"),shared=nets("198.51.100.0/24"))
        self.assertEqual(len(rows),3)
        self.assertEqual(summary(rows)["current_ip_lst"],2)
        self.assertEqual(summary(rows)["by_class"]["OTHER"]["exact_service_claim"],1)
        self.assertEqual([x for x in rows if x["origin_class"]=="SHARED_INFRA"][0]["review_priority"],
                         "P1_CURRENT_HARD_SHARED_OR_OTHER")
        self.assertEqual([x for x in rows if x["origin_class"]=="CORE_CORPORATE"][0]["review_priority"],
                         "P2_CURRENT_HARD_CORE")

    def test_network_boundary_addresses_are_not_dropped(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"nets.txt"
            path.write_text("192.0.2.0/30\n")
            ips=read_ip_hosts(path)
            self.assertEqual(len(ips),4)
            self.assertIn(ipaddress.ip_address("192.0.2.0"),ips)
            self.assertIn(ipaddress.ip_address("192.0.2.3"),ips)

    def test_duplicate_class_fails_closed(self):
        groups={"CORE_CORPORATE":{ipaddress.ip_address("192.0.2.1")},
                "SHARED_INFRA":{ipaddress.ip_address("192.0.2.1")},
                "OTHER":set()}
        with self.assertRaisesRegex(ValueError,"classified twice"):
            build_matrix(groups,[],{},set(),set())

if __name__=="__main__":
    unittest.main()
