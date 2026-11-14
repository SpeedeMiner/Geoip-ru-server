import io
import json
import tarfile
import tempfile
import unittest
from ipaddress import ip_network
from pathlib import Path

from audit_v41_non_dns_candidates import match_archive, partition
from build_v41_overlay import interval_size, intervals


class NonDnsDiscoveryTest(unittest.TestCase):
    def test_longest_prefix_preserves_equal_length_moas_and_unobserved(self):
        pool = intervals({ip_network("192.0.2.0/24"), ip_network("198.51.100.7/32")}, 4)
        observed = {ip_network("192.0.2.0/24"): {1}, ip_network("192.0.2.0/25"): {2, 3}}
        self.assertEqual([(str(n), asns, interval_size(win)) for n, asns, win in partition(pool, observed)],
                         [("192.0.2.0/25", [2, 3], 128), ("192.0.2.0/24", [1], 128), ("None", [], 1)])

    def test_archive_matches_boundaries_and_deduplicates_origins(self):
        scope = intervals({ip_network("192.0.2.127/32"), ip_network("192.0.2.255/32")}, 4)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                for asn, routes in [(2, ["0.0.0.0/0", "192.0.2.0/25", "192.0.2.0/25", "192.0.2.128/26"]),
                                    (3, ["192.0.2.0/25", "192.0.2.192/26"])]:
                    data = json.dumps({"asn": asn, "prefixes": {"ipv4": routes}}).encode()
                    info = tarfile.TarInfo(f"archive/{asn}/aggregated.json")
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
            matches, _ = match_archive(path, scope)
        self.assertEqual(dict(matches), {ip_network("192.0.2.0/25"): {2, 3},
                                         ip_network("192.0.2.192/26"): {3}})
