from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_geoip_source_catalog import (  # noqa: E402
    CatalogError,
    DEFAULT_CATALOG,
    validate_catalog,
)


class GeoIPSourceCatalogTests(unittest.TestCase):
    def _temp_catalog(self, content: str):
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "catalog.tsv"
        path.write_text(content, encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return path

    def test_current_catalog_has_unique_rows_and_required_sources(self):
        result = validate_catalog(DEFAULT_CATALOG)
        self.assertEqual(result["rows"], 38)
        self.assertEqual(result["unique_source_ids"], 38)
        self.assertGreaterEqual(result["required_ids"], 25)

    def test_duplicate_source_id_is_rejected(self):
        content = DEFAULT_CATALOG.read_text(encoding="utf-8")
        lines = content.splitlines()
        duplicate = next(line for line in lines[1:] if line.startswith("geoip-hydra\t"))
        with self.assertRaisesRegex(CatalogError, "duplicate SOURCE_ID"):
            validate_catalog(self._temp_catalog(content + duplicate + "\n"))

    def test_non_https_fallback_is_rejected(self):
        content = DEFAULT_CATALOG.read_text(encoding="utf-8")
        changed = content.replace(
            "https://cdn.jsdelivr.net/gh/hydraponique/",
            "http://cdn.jsdelivr.net/gh/hydraponique/",
            1,
        )
        with self.assertRaisesRegex(CatalogError, "non-HTTPS"):
            validate_catalog(self._temp_catalog(changed))

    def test_missing_required_source_id_is_rejected(self):
        content = DEFAULT_CATALOG.read_text(encoding="utf-8")
        lines = [
            line for line in content.splitlines()
            if not line.startswith("rir-afrinic\t")
        ]
        with self.assertRaisesRegex(CatalogError, "missing required production source IDs"):
            validate_catalog(self._temp_catalog("\n".join(lines) + "\n"))

    def test_candidate_only_semantics_cannot_be_promoted_silently(self):
        content = DEFAULT_CATALOG.read_text(encoding="utf-8")
        changed = content.replace(
            "geoip-hydra\tDIRECT_CANDIDATE\thydra-geoip.dat",
            "geoip-hydra\tDIRECT_CANDIDATE\thydra-geoip.dat",
            1,
        )
        old = "\tCANDIDATE_ONLY\tOnly direct and whitelist categories become diagnostic candidates"
        new = "\tCORE_GEOGRAPHIC_RU\tOnly direct and whitelist categories become diagnostic candidates"
        self.assertIn(old, changed)
        changed = changed.replace(old, new, 1)
        with self.assertRaisesRegex(CatalogError, "production role drifted"):
            validate_catalog(self._temp_catalog(changed))


if __name__ == "__main__":
    unittest.main()
