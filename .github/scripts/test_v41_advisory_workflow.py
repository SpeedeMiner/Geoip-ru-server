"""Protect the advisory-only and PR-only execution boundary."""
from pathlib import Path
import unittest

import yaml


class AdvisoryWorkflowTests(unittest.TestCase):
    def test_diagnostics_are_pr_only_and_cannot_gate_publication(self):
        path = Path(__file__).resolve().parents[1] / 'workflows/geoip-v41.yml'
        workflow = yaml.safe_load(path.read_text(encoding='utf-8'))
        steps = workflow['jobs']['build']['steps']
        names = {
            'Pin the release for ASN and provider advisories (PR only)',
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


if __name__ == '__main__':
    unittest.main()
