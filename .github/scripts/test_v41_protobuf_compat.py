"""Cross-check the encoder with the existing independent strict wire reader.

The companion Go test decodes Python output using the actual upstream protobuf
types pinned in geoip-v37-builder/go.mod, rather than a second hand-written codec.
"""
import ipaddress
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_v41_overlay import encode_geoip
from validate_v41_publication_bounds import read


class ProtobufCompatibilityTests(unittest.TestCase):
    def test_categories_and_host_masks_with_independent_reader(self):
        entries = {
            "RU": {ipaddress.ip_network("192.0.2.1/32"), ipaddress.ip_network("2001:db8::1/128")},
            "PRIVATE": {ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("fc00::/7")},
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.dat"
            path.write_bytes(encode_geoip(entries))
            actual, _ = read(path)
        self.assertEqual(set(actual), set(entries))
        for category, networks in entries.items():
            for family in (4, 6):
                expected = sorted((int(n.network_address), int(n.broadcast_address))
                                  for n in networks if n.version == family)
                self.assertEqual(actual[category][family], expected)


if __name__ == "__main__":
    unittest.main()
