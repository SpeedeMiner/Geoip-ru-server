import datetime as dt
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from build_rir_rukzby_prefixes import REGISTRIES, build, parse_resource, snapshot_header, utc_today, validate_snapshot_age


class RegionalRirInventoryTests(unittest.TestCase):
    def test_ipv4_resource_expands_to_minimal_cidrs(self):
        self.assertEqual(parse_resource("RU", "ipv4", "192.0.2.0", "256"), ["192.0.2.0/24"])

    def test_ipv6_resource_uses_prefix_length(self):
        self.assertEqual(parse_resource("KZ", "ipv6", "2001:db8:1::", "48"), ["2001:db8:1::/48"])

    def test_rejects_wrong_family_and_default_route(self):
        self.assertEqual(parse_resource("RU", "ipv4", "2001:db8::", "2"), [])
        self.assertEqual(parse_resource("RU", "ipv6", "::", "0"), [])

    def test_snapshot_header_requires_matching_registry(self):
        with self.assertRaises(ValueError):
            snapshot_header(["2|apnic|3|20260101|20260101|20260101|1"], "arin")

    def test_build_keeps_country_registry_and_status_provenance(self):
        today = utc_today().strftime("%Y%m%d")
        content = "\n".join([
            f"2|afrinic|3|20200101|20200101|{today}|1",
            f"afrinic|RU|ipv4|192.0.2.0|256|20200101|allocated",
            f"afrinic|BY|ipv6|2001:db8:1::|48|20200101|assigned",
            f"afrinic|KZ|ipv4|198.51.100.0|256|20200101|legacy",
            f"afrinic|RU|ipv4|203.0.113.0|256|20200101|available",
            "",
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "afrinic"
            path.write_text(content, encoding="utf-8")
            rows, _ = build({name: path if name == "afrinic" else _stub_snapshot(name, tmp, today) for name in ("afrinic", "apnic", "arin", "lacnic", "ripencc")})
        self.assertEqual({(r["country"], r["prefix"], r["registry"], r["status"]) for r in rows}, {
            ("RU", "192.0.2.0/24", "afrinic", "allocated"),
            ("BY", "2001:db8:1::/48", "afrinic", "assigned"),
            ("KZ", "198.51.100.0/24", "afrinic", "legacy"),
        })

    def test_freshness_boundary_is_inclusive_for_both_parsers(self):
        reference = dt.date(2026, 1, 15)
        for age in (-1, 0, 14):
            with self.subTest(age=age):
                validate_snapshot_age("arin", reference - dt.timedelta(days=age), reference)
        for age in (-2, 15):
            with self.subTest(age=age), self.assertRaisesRegex(ValueError, "as of 2026-01-15 UTC"):
                validate_snapshot_age("arin", reference - dt.timedelta(days=age), reference)

    def test_both_clis_replay_old_inputs_without_weakening_live_freshness(self):
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as tmp:
            paths = [_stub_snapshot(name, tmp, "20200102") for name in REGISTRIES]
            with paths[-1].open("a", encoding="utf-8") as stream:
                stream.write("ripencc|RU|ipv4|192.0.2.0|256|20200101|allocated\n")
                for country, start in (("RU", 64500), ("BY", 64600), ("KZ", 64700)):
                    stream.write(f"ripencc|{country}|asn|{start}|25|20200101|allocated\n")
            regional, legacy = (Path(tmp) / name for name in ("regional", "legacy"))
            regional_stats, legacy_stats = (Path(tmp) / name for name in ("regional.stats", "legacy.stats"))
            commands = (
                ([scripts / "build_rir_rukzby_prefixes.py",
                  *(arg for name, path in zip(REGISTRIES, paths) for arg in (f"--{name}", path)),
                  "--output", regional, "--stats", regional_stats], regional, regional_stats),
                ([scripts / "build_v41_rir_legacy_inventory.py", *paths, Path(tmp) / "asn",
                  legacy, legacy_stats, Path(tmp) / "by-kz"], legacy, legacy_stats),
            )
            for command, data, stats in commands:
                with self.subTest(script=command[0].name):
                    for args, error in (([], "stale/future"), (["--as-of", "2020-01-17"], "15 days old"),
                                        (["--as-of", "9999-01-01"], "no later than today"),
                                        (["--as-of", "20200102"], "YYYY-MM-DD")):
                        bad = subprocess.run([sys.executable, *command, *args], capture_output=True, text=True)
                        self.assertNotEqual(bad.returncode, 0, bad.stdout)
                        self.assertIn(error, bad.stderr)
                        self.assertFalse(data.exists())
                        self.assertFalse(stats.exists())
                    replay = subprocess.run([sys.executable, *command, "--as-of", "2020-01-03"],
                                            capture_output=True, text=True)
                    self.assertEqual(replay.returncode, 0, replay.stderr)
                    self.assertIn("192.0.2.0/24", data.read_text())
                    self.assertIn("Freshness reference UTC date: 2020-01-03", stats.read_text())


def _stub_snapshot(registry, tmp, today):
    p = Path(tmp) / registry
    p.write_text(f"2|{registry}|3|20200101|20200101|{today}|1\n", encoding="utf-8")
    return p


if __name__ == "__main__":
    unittest.main()
