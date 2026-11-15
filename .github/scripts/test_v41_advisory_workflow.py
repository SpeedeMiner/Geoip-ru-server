"""Protect the advisory-only and PR-only execution boundary."""
from pathlib import Path
import hashlib
import os
import subprocess
from tempfile import TemporaryDirectory
import unittest

import yaml


class AdvisoryWorkflowTests(unittest.TestCase):
    @staticmethod
    def run_baseline_fixture(*, fail_fetch=False, bad_checksum=False):
        path = Path(__file__).resolve().parents[1] / 'workflows/geoip-v41.yml'
        workflow = yaml.safe_load(path.read_text(encoding='utf-8'))
        step = next(s for s in workflow['jobs']['build']['steps'] if s.get('id') == 'advisory_baseline')
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / 'bin'
            bindir.mkdir()
            git = bindir / 'git'
            git.write_text('''#!/bin/sh
case "$1" in
  fetch) [ "$TEST_FAIL_FETCH" = 0 ] ;;
  rev-parse) printf '%s\\n' "$TEST_RELEASE_SHA" ;;
  show) case "$2" in
    *:geoip_RU.dat) printf 'fixture' ;;
    *:geoip_RU.dat.sha256sum) printf '%s  geoip_RU.dat\\n' "$TEST_CHECKSUM" ;;
    *) exit 2 ;;
  esac ;;
  *) exit 2 ;;
esac
''')
            git.chmod(0o755)
            output, summary = root / 'output', root / 'summary'
            output.touch()
            summary.touch()
            checksum = hashlib.sha256(b'fixture').hexdigest()
            env = {**os.environ, 'PATH': str(bindir) + os.pathsep + os.environ['PATH'],
                   'RUNNER_TEMP': str(root), 'GITHUB_OUTPUT': str(output),
                   'GITHUB_STEP_SUMMARY': str(summary), 'TEST_RELEASE_SHA': 'a' * 40,
                   'TEST_FAIL_FETCH': '1' if fail_fetch else '0',
                   'TEST_CHECKSUM': '0' * 64 if bad_checksum else checksum}
            result = subprocess.run(['bash', '-c', step['run']], env=env, capture_output=True, text=True)
            return result.returncode, output.read_text(), summary.read_text()

    def test_release_is_exported_only_after_checksum_validation(self):
        code, output, summary = self.run_baseline_fixture()
        self.assertEqual(code, 0)
        self.assertEqual(output, 'release_sha=' + 'a' * 40 + '\n')
        self.assertIn('All advisory comparison baseline', summary)
        for flags in ({'fail_fetch': True}, {'bad_checksum': True}):
            with self.subTest(flags=flags):
                code, output, summary = self.run_baseline_fixture(**flags)
                self.assertNotEqual(code, 0)
                self.assertNotIn('release_sha=', output)
                self.assertIn('comparisons are unknown', summary)

    def test_diagnostics_are_pr_only_and_cannot_gate_publication(self):
        path = Path(__file__).resolve().parents[1] / 'workflows/geoip-v41.yml'
        workflow = yaml.safe_load(path.read_text(encoding='utf-8'))
        steps = workflow['jobs']['build']['steps']
        names = {
            'Pin one release for all PR advisories',
            'Report priority ASN and IPv6 coverage (PR only)',
            'Capture current scoped provider feeds (PR only)',
            'Report scoped provider and Hydra provenance (PR only)',
            'Upload ASN and scoped provider advisories (PR only)',
        }
        selected = [step for step in steps if step.get('name') in names]
        self.assertEqual({step['name'] for step in selected}, names)
        for step in selected:
            with self.subTest(step=step['name']):
                self.assertIn("github.event_name == 'pull_request'", step.get('if', ''))
                self.assertIs(step.get('continue-on-error'), True)
        publisher = str(workflow['jobs']['publish'])
        self.assertNotIn('audit_v41_asn_regressions.py', publisher)
        self.assertNotIn('audit_v41_direct_provenance.py', publisher)
        upload = next(step for step in selected if step['name'].startswith('Upload'))
        self.assertEqual(upload['with']['name'], 'geoip-v41-asn-provider-advisories')
        self.assertEqual(upload['with']['if-no-files-found'], 'warn')

    def test_all_comparisons_share_one_verified_release_or_report_unknown(self):
        path = Path(__file__).resolve().parents[1] / 'workflows/geoip-v41.yml'
        workflow = yaml.safe_load(path.read_text(encoding='utf-8'))
        steps = workflow['jobs']['build']['steps']
        baseline = next(step for step in steps if step.get('id') == 'advisory_baseline')
        self.assertIn('sha256sum -c', baseline['run'])
        self.assertIn('comparisons are unknown', baseline['run'])
        for name in ('Report exact DIRECT delta against a pinned release (PR only)',
                     'Report exact Antifilter delta and last verified live resolver input',
                     'Report priority ASN and IPv6 coverage (PR only)',
                     'Report scoped provider and Hydra provenance (PR only)'):
            step = next(s for s in steps if s.get('name') == name)
            with self.subTest(name=name):
                self.assertIn('steps.advisory_baseline.outputs.release_sha', step['env']['ADVISORY_RELEASE_SHA'])
                self.assertNotIn('refs/heads/release', step['run'])
        for name in ('Report exact DIRECT delta against a pinned release (PR only)',
                     'Report exact Antifilter delta and last verified live resolver input',
                     'Report scoped provider and Hydra provenance (PR only)'):
            step = next(s for s in steps if s.get('name') == name)
            self.assertIn("steps.advisory_baseline.outputs.release_sha != ''", step['if'])


if __name__ == '__main__':
    unittest.main()
