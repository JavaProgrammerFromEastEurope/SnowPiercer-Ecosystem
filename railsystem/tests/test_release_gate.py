import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from railsystem.release_gate import evaluate, write_report
from railsystem.verification import manifest

ROOT = Path(__file__).resolve().parents[1]
GOOD = {'tests_run': 1, 'successful': True, 'failures': [], 'errors': [], 'skipped': 0}

class ReleaseGateTests(unittest.TestCase):
    def test_blocked_without_baseline(self):
        r = evaluate(ROOT, regression=GOOD)
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertEqual(r['gates']['integrity']['status'], 'BLOCKED')
    def test_pass_with_baseline(self):
        self.assertEqual(evaluate(ROOT, expected_manifest=manifest(ROOT), regression=GOOD)['status'], 'PASS')
    def test_mismatch_fails(self):
        baseline = manifest(ROOT)
        baseline['files']['fake'] = 'abc'
        self.assertEqual(evaluate(ROOT, expected_manifest=baseline, regression=GOOD)['status'], 'FAIL')
    def test_regression_failure(self):
        bad = dict(GOOD, successful=False)
        self.assertEqual(evaluate(ROOT, expected_manifest=manifest(ROOT), regression=bad)['status'], 'FAIL')
    def test_zero_tests_fail(self):
        self.assertEqual(evaluate(ROOT, regression=dict(GOOD, tests_run=0))['status'], 'FAIL')
    def test_skipped_fail(self):
        self.assertEqual(evaluate(ROOT, regression=dict(GOOD, skipped=1))['status'], 'FAIL')
    def test_errors_fail(self):
        self.assertEqual(evaluate(ROOT, regression=dict(GOOD, errors=['error']))['status'], 'FAIL')
    def test_failures_fail(self):
        self.assertEqual(evaluate(ROOT, regression=dict(GOOD, failures=['fail']))['status'], 'FAIL')
    def test_missing_test_blocks_regression(self):
        with patch('railsystem.release_gate.coverage', side_effect=__import__('railsystem.verification', fromlist=['VerificationError']).VerificationError('missing')):
            self.assertEqual(evaluate(ROOT, regression=GOOD)['gates']['regression']['status'], 'BLOCKED')
    def test_report_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/'report.json'
            write_report({'status':'BLOCKED'}, dest)
            self.assertEqual(json.loads(dest.read_text())['status'], 'BLOCKED')
    def test_schema(self):
        self.assertEqual(evaluate(ROOT, regression=GOOD)['schema_version'], 1)
    def test_scope(self):
        self.assertIn('not permission', evaluate(ROOT, regression=GOOD)['scope'])
