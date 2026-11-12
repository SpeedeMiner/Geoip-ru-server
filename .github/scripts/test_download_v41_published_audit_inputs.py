import hashlib
import unittest

from download_v41_published_audit_inputs import INPUTS, validate_and_download


class PublishedReleaseVerifierTests(unittest.TestCase):
    def fixture(self):
        data = {name: ("payload:" + name).encode() for name in INPUTS}
        effective = b"192.0.2.1/32\n"
        data["geoip_RU_v41_blocked_ip_exclusions.txt"] = effective
        sha = lambda value: hashlib.sha256(value).hexdigest()
        data["geoip_RU_v41_blocked_ip_exclusions.txt.sha256sum"] = (
            sha(effective) + "  geoip_RU_v41_blocked_ip_exclusions.txt\n"
        ).encode()
        manifest = {"schema": 2, "output_sha256": sha(data["geoip_RU.dat"]),
                    "input_sha256": {
                        key: sha(data[name]) for name, (_, key) in INPUTS.items()
                        if name != "geoip_RU.dat"
                    }}
        return data, manifest

    def test_valid_complete_release_snapshot(self):
        data, manifest = self.fixture()
        result = validate_and_download(manifest, lambda key: data[key])
        self.assertEqual(result["geoip_RU.dat"], data["geoip_RU.dat"])
        self.assertEqual(len(result), len(INPUTS) + 1)

    def test_modified_hard_source_rejected(self):
        data, manifest = self.fixture()
        data["geoip_RU_blocked_ip_exact_and_legacy_hard.txt"] = b"changed"
        with self.assertRaisesRegex(ValueError, "hash differs"):
            validate_and_download(manifest, lambda key: data[key])

    def test_modified_effective_block_rejected(self):
        data, manifest = self.fixture()
        data["geoip_RU_v41_blocked_ip_exclusions.txt"] = b"changed"
        with self.assertRaisesRegex(ValueError, "hash differs"):
            validate_and_download(manifest, lambda key: data[key])

    def test_missing_expected_hash_fails_closed(self):
        data, manifest = self.fixture()
        del manifest["input_sha256"]["corporate_core_prefixes"]
        with self.assertRaisesRegex(ValueError, "missing an input SHA256"):
            validate_and_download(manifest, lambda key: data[key])


if __name__ == "__main__":
    unittest.main()
