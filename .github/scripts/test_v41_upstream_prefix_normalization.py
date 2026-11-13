from datetime import date
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent


class UpstreamPrefixNormalizationTests(unittest.TestCase):
    def test_legacy_rir_ipv6_preserves_prefix_length_and_normalizes_host_bits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            date_token = date.today().strftime("%Y%m%d")
            sources = []
            for registry in ("afrinic", "apnic", "arin", "lacnic", "ripencc"):
                p = root / registry
                data = f"2|{registry}|0|0|{date_token}|{date_token}|+0000\n"
                if registry == "ripencc":
                    data += (
                        f"ripencc|RU|asn|100|25|{date_token}|allocated\n"
                        f"ripencc|BY|asn|200|12|{date_token}|allocated\n"
                        f"ripencc|KZ|asn|300|13|{date_token}|allocated\n"
                        f"ripencc|RU|ipv6|2a01:abcd::1|32|{date_token}|allocated\n"
                        f"ripencc|RU|ipv6|2a01:abce::|32|{date_token}|assigned\n"
                        f"ripencc|RU|ipv6|2a01:abcf::1|129|{date_token}|allocated\n"
                        f"ripencc|RU|ipv6|192.0.2.7|24|{date_token}|allocated\n"
                    )
                p.write_text(data, encoding="utf-8")
                sources.append(p)
            asn, prefixes, stats, by_kz = (root / name for name in ("asn", "prefixes", "stats", "by-kz"))
            run = subprocess.run(
                [sys.executable, SCRIPTS / "build_v41_rir_legacy_inventory.py",
                 *sources, asn, prefixes, stats, by_kz],
                text=True, capture_output=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual([s for s in prefixes.read_text().splitlines() if not s.startswith("#")],
                             ["2a01:abcd::/32", "2a01:abce::/32"])
            self.assertIn("Non-canonical RU IPv6 resource rows normalized: 1", stats.read_text())
