from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_rir_residual_bgp_origin_evidence import (  # noqa: E402
    EvidenceError,
    build_evidence,
)


def add_json_member(archive: tarfile.TarFile, name: str, item: dict) -> None:
    raw = json.dumps(item, separators=(",", ":")).encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(raw)
    archive.addfile(info, io.BytesIO(raw))


class RIRResidualBGPOriginEvidenceTests(unittest.TestCase):
    def _fixture(self, root: Path) -> argparse.Namespace:
        residual = root / "rir-residual.tsv"
        residual.write_text(
            "PREFIX\tFAMILY\tPREFIX_ADDRESSES\tUNEXPLAINED_OUTSIDE_RU_PRIVATE_BLOCKED_ADDRESSES\tSTATUS\n"
            "203.0.113.0/24\tIPv4\t256\t256\tREVIEW\n"
            "198.51.100.0/24\tIPv4\t256\t256\tREVIEW\n",
            encoding="utf-8",
        )
        inventory = root / "inventory.tsv"
        inventory.write_text(
            "PREFIX\tIN_GLOBAL_BGP_90D_OBSERVATIONS\tIN_SELECTED_RIR_OR_COMPANY_ORIGIN_BGP\tIN_ACCEPTED_ADDITIONAL_GEOIP_FEEDS\n"
            "203.0.113.0/24\tyes\tno\tno\n"
            "198.51.100.0/24\tno\tno\tno\n",
            encoding="utf-8",
        )
        archive_path = root / "ipverse.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            add_json_member(archive, "ipverse/AS13335/aggregated.json", {
                "asn": 13335, "metadata": {"countryCode": "US"},
                "prefixes": {"ipv4": ["203.0.113.0/24"], "ipv6": []},
            })
            add_json_member(archive, "ipverse/AS64500/aggregated.json", {
                "asn": 64500, "metadata": {"countryCode": "ZZ"},
                "prefixes": {"ipv4": ["203.0.113.0/24"], "ipv6": []},
            })
        return argparse.Namespace(
            residual=residual,
            inventory=inventory,
            bgp_archive=archive_path,
            output=root / "exact-origins.tsv",
            stats=root / "exact-origins-stats.txt",
        )

    def test_exact_moas_is_joined_and_missing_exact_route_stays_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self._fixture(Path(tmp))
            result = build_evidence(args)
            with args.output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            by_prefix = {row["PREFIX"]: row for row in rows}
            self.assertEqual(result["prefixes"], 2)
            self.assertEqual(result["exact_observed"], 1)
            self.assertEqual(result["exact_not_observed"], 1)
            self.assertEqual(result["exact_moas"], 1)
            self.assertEqual(by_prefix["203.0.113.0/24"]["GLOBAL_BGP_90D_EXACT_OBSERVATION"], "OBSERVED")
            self.assertEqual(by_prefix["203.0.113.0/24"]["GLOBAL_BGP_90D_EXACT_ORIGIN_ASNS"], "AS13335,AS64500")
            self.assertEqual(
                by_prefix["203.0.113.0/24"]["GLOBAL_BGP_90D_EXACT_ORIGIN_COUNTRY_CODES"],
                "AS13335=US,AS64500=ZZ",
            )
            self.assertEqual(by_prefix["203.0.113.0/24"]["GLOBAL_BGP_90D_EXACT_MOAS"], "yes")
            self.assertEqual(by_prefix["198.51.100.0/24"]["GLOBAL_BGP_90D_EXACT_OBSERVATION"], "NOT_OBSERVED_IN_90D_SNAPSHOT")
            self.assertEqual(by_prefix["198.51.100.0/24"]["GLOBAL_BGP_90D_EXACT_ORIGIN_ASNS"], "")
            self.assertTrue(all(row["STATUS"] == "REVIEW" for row in rows))
            stats = args.stats.read_text(encoding="utf-8")
            self.assertIn("missing exact route in this rolling 90-day snapshot is not proof", stats)

    def test_rejects_non_review_residual_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self._fixture(Path(tmp))
            content = args.residual.read_text(encoding="utf-8").replace("203.0.113.0/24\tIPv4\t256\t256\tREVIEW", "203.0.113.0/24\tIPv4\t256\t256\tADD")
            args.residual.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(EvidenceError, "non-REVIEW"):
                build_evidence(args)


if __name__ == "__main__":
    unittest.main()
