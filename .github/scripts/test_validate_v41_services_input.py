import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validate_v41_services_input import validate


class ServicesInputTests(unittest.TestCase):
    def test_minimum_valid_service_count_and_corruption(self):
        service = {"name": "example", "tier": "standard", "ipv4": ["192.0.2.1/32"], "ipv6": []}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "services.json"
            def write(rows):
                path.write_text(json.dumps({"categories": [{"id": "test", "services": rows}]}), encoding="utf-8")
            write([service] * 50)
            self.assertEqual(validate(path), {"services": 50, "unique_prefixes": 1})
            write([service] * 49)
            with self.assertRaisesRegex(ValueError, "unexpectedly small"):
                validate(path)
            write([service] * 50 + [None])
            with self.assertRaisesRegex(ValueError, "invalid service"):
                validate(path)
