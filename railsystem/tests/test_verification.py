import json
import tempfile
import unittest
from pathlib import Path
from railsystem.verification import (STAGE_TESTS, VerificationError, coverage, evidence,
                                     manifest, sha256_file, stage_for_test, verify_manifest,
                                     write_evidence)

ROOT = Path(__file__).resolve().parents[1]

class VerificationTests(unittest.TestCase):
    def test_mapping(self): self.assertEqual(stage_for_test('test_operations.py'), 'RAIL-OPS-001')
    def test_mapping_rejects_unknown(self):
        with self.assertRaises(VerificationError): stage_for_test('test_unknown.py')
    def test_all_stages_covered(self): self.assertEqual(set(coverage(ROOT)), set(STAGE_TESTS))
    def test_architecture_legacy_test(self): self.assertIn('test_contracts.py', coverage(ROOT)['RAIL-ARCH-001'])
    def test_manifest_deterministic(self): self.assertEqual(manifest(ROOT), manifest(ROOT))
    def test_manifest_contains_sources(self): self.assertIn('railsystem/verification.py', manifest(ROOT)['files'])
    def test_manifest_sha256(self): self.assertEqual(len(sha256_file(Path(__file__))), 64)
    def test_manifest_round_trip(self): self.assertTrue(verify_manifest(ROOT, manifest(ROOT)))
    def test_manifest_rejects_tamper(self):
        data = manifest(ROOT)
        data['files']['railsystem/verification.py'] = '0' * 64
        self.assertFalse(verify_manifest(ROOT, data))
    def test_manifest_rejects_invalid(self):
        with self.assertRaises(VerificationError): verify_manifest(ROOT, {})
    def test_missing_root(self):
        with self.assertRaises(VerificationError): manifest(Path('/missing-railsystem-verify-root'))
    def test_timestamp_rejects_missing(self):
        with self.assertRaises(VerificationError): evidence(ROOT, timestamp='today')
    def test_timestamp_rejects_invalid_calendar(self):
        with self.assertRaises(VerificationError): evidence(ROOT, timestamp='2026-02-30T00:00:00Z')
    def test_write_inside_source_rejected(self):
        with self.assertRaises(VerificationError): write_evidence(ROOT, ROOT/'report.json', timestamp='2026-11-14T00:00:00Z')
    def test_manifest_ignores_cache(self):
        self.assertFalse(any('__pycache__' in name for name in manifest(ROOT)['files']))
    def test_manifest_sorted(self):
        keys = list(manifest(ROOT)['files']); self.assertEqual(keys, sorted(keys))
