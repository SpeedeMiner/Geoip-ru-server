from hashlib import sha256
from io import StringIO
import ipaddress
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_v41_overlay import encode_geoip
from report_v41_direct_delta import make_report, write_summary
from v41_reviewed_ipv6_admission import RECORD_KEY, read_reviewed_ipv6_admission


class DirectDeltaTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.table = Path(__file__).resolve().parents[1] / "data/v41-reviewed-ipv6-admission-exclusions.tsv"
        self.policy = read_reviewed_ipv6_admission(self.table)
        self.keep = ("2a0b:4e07:6301::/48", "2a0b:4e07:63ff::/48", "2001:ad0:2000:1::/64")
        self.v4 = "192.0.2.1/32"
        self.sha = "a" * 40

    def dat(self, path, ru, private=("10.0.0.0/8", "fc00::/7")):
        output = self.root / path
        output.write_bytes(encode_geoip({
            name: {ipaddress.ip_network(n) for n in items}
            for name, items in (("RU", ru), ("PRIVATE", private))
        }))
        return output

    def fixtures(self, before, after, *, private=("10.0.0.0/8", "fc00::/7")):
        old = self.dat("old.dat", before)
        new = self.dat("new.dat", after, private)
        checksum = self.root / "old.sha256sum"
        checksum.write_text(f"{sha256(old.read_bytes()).hexdigest()}  geoip_RU.dat\n")
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({
            "output_sha256": sha256(new.read_bytes()).hexdigest(),
            "input_sha256": {RECORD_KEY: sha256(self.table.read_bytes()).hexdigest()},
            RECORD_KEY: {"records": list(self.policy.values())},
        }))
        return old, checksum, self.sha, new, manifest, self.table

    def test_four_reviewed_rows_remain_individual_if_exact_delta_collapses(self):
        after = [self.v4, *self.keep]
        report = make_report(*self.fixtures([*after, *map(str, self.policy)], after))
        reviewed = report["ipv6_removals"]
        self.assertEqual(reviewed["covered_by_reviewed_policy"]["addresses"], str(4 * 2**80))
        self.assertIn("2a0b:4e07:63f0::/47", reviewed["covered_by_reviewed_policy"]["cidrs"])
        self.assertEqual([r["policy_prefix"] for r in reviewed["reviewed_policy_rows"]], list(map(str, sorted(self.policy))))
        self.assertEqual(reviewed["outside_reviewed_policy"], {"addresses": "0", "cidrs": []})
        self.assertEqual(report["baseline"]["release_commit"], self.sha)

    def test_partial_policy_overlap_and_unexplained_host_remain_separate(self):
        keep = [self.v4, *self.keep]
        lost = "2001:db8::1/128"
        partial = "2a0b:4e07:6300::/49"
        report = make_report(*self.fixtures([*keep, lost, partial], [*keep, "192.0.2.2/32"]))
        reviewed = report["ipv6_removals"]
        self.assertEqual(reviewed["covered_by_reviewed_policy"]["cidrs"], [partial])
        self.assertEqual(reviewed["outside_reviewed_policy"], {"addresses": "1", "cidrs": [lost]})
        self.assertEqual(report["direct"]["ipv4"]["added"]["cidrs"], ["192.0.2.2/32"])
        summary = StringIO()
        write_summary(report, summary)
        self.assertIn(lost, summary.getvalue())

    def test_unchanged_direct_does_not_hide_changed_private(self):
        keep = [self.v4, *self.keep]
        report = make_report(*self.fixtures(keep, keep, private=("10.0.0.0/8", "fd00::/8")))
        self.assertEqual(report["private_changed"], {"ipv4": False, "ipv6": True})
        self.assertTrue(all(item == {"addresses": "0", "cidrs": []}
                            for family in report["direct"].values() for item in family.values()))

    def test_untrusted_reference_or_candidate_is_not_a_zero_delta(self):
        keep = [self.v4, *self.keep]
        args = self.fixtures(keep, keep)
        args[1].write_text(f"{'f' * 64}  geoip_RU.dat\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            make_report(*args)
        args = self.fixtures(keep, keep)
        policy = json.loads(args[4].read_text())
        policy[RECORD_KEY]["records"] = []
        args[4].write_text(json.dumps(policy))
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            make_report(*args)

    def test_candidate_cannot_restore_a_reviewed_prefix(self):
        keep = [self.v4, *self.keep]
        with self.assertRaisesRegex(ValueError, "intersects reviewed"):
            make_report(*self.fixtures(keep, [*keep, "2a0b:4e07:6300::/48"]))

    def test_workflow_runs_advisory_only_outside_publisher(self):
        workflow = (self.table.parents[1] / "workflows/geoip-v41.yml").read_text()
        build, publisher = workflow.split("\n  publish:\n", 1)
        self.assertIn('--candidate "$V41_OUTPUT_FILE" --absolute-only', build)
        self.assertNotIn('--reference "$V41_OUTPUT_FILE"', build)
        report = build.split("      - name: Report exact DIRECT delta", 1)[1]
        for step in report.split("\n      - name: ")[:2]:
            self.assertIn("github.event_name == 'pull_request'", step)
            self.assertIn("github.ref == 'refs/heads/main'", step)
            self.assertIn("continue-on-error: true", step)
        self.assertNotIn("report_v41_direct_delta.py", publisher)
