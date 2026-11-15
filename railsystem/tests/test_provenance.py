import copy
import tempfile
import unittest
from pathlib import Path
from railsystem.provenance import candidate_baseline, validate_baseline, canonical_digest, assess, ProvenanceError

class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('railsystem','tests','docs','architecture','requirements','safety','interfaces'):
            (self.root/name).mkdir()
        (self.root/'docs'/'a.md').write_text('a')
        # assess uses the full registered inventory; isolated fixtures deliberately fail inventory.
    def test_candidate_valid(self):
        self.assertEqual(validate_baseline(candidate_baseline(self.root, 'v1'))['baseline_id'], 'v1')
    def test_candidate_deterministic(self):
        self.assertEqual(candidate_baseline(self.root, 'v1'), candidate_baseline(self.root, 'v1'))
    def test_bad_id(self):
        with self.assertRaises(ProvenanceError): candidate_baseline(self.root, '../bad')
    def test_digest_tamper(self):
        b = candidate_baseline(self.root, 'v1'); b['manifest_digest'] = '0'*64
        with self.assertRaises(ProvenanceError): validate_baseline(b)
    def test_file_digest_tamper(self):
        b = candidate_baseline(self.root, 'v1'); b['manifest']['files']['docs/a.md'] = 'z'*64
        b['manifest_digest'] = canonical_digest(b['manifest'])
        with self.assertRaises(ProvenanceError): validate_baseline(b)
    def test_traversal(self):
        b = candidate_baseline(self.root, 'v1'); b['manifest']['files']['../x'] = '0'*64
        b['manifest_digest'] = canonical_digest(b['manifest'])
        with self.assertRaises(ProvenanceError): validate_baseline(b)
    def test_missing_baseline_blocks(self):
        self.assertEqual(assess(self.root, baseline=None, approval=None, evidence=None)['gates']['baseline']['status'], 'BLOCKED')
    def test_no_approval_never_passes(self):
        b = candidate_baseline(self.root, 'v1')
        self.assertNotEqual(assess(self.root, baseline=b, approval=None, evidence=None)['status'], 'PASS')
    def test_mismatch_integrity_fails(self):
        b = candidate_baseline(self.root, 'v1'); (self.root/'docs'/'a.md').write_text('changed')
        self.assertEqual(assess(self.root, baseline=b, approval=None, evidence=None)['gates']['integrity']['status'], 'FAIL')
    def test_invalid_approval_fails(self):
        b = candidate_baseline(self.root, 'v1')
        self.assertEqual(assess(self.root, baseline=b, approval={'baseline_id':'other'}, evidence=None)['gates']['approval']['status'], 'FAIL')
    def test_forged_approval_blocks(self):
        b = candidate_baseline(self.root, 'v1')
        self.assertEqual(assess(self.root, baseline=b, approval={'baseline_id':'v1','approved':True}, evidence=None)['gates']['approval']['status'], 'BLOCKED')
    def test_missing_evidence_blocks(self):
        self.assertEqual(assess(self.root, baseline=None, approval=None, evidence=None)['gates']['evidence']['status'], 'BLOCKED')
    def test_bad_evidence_fails(self):
        self.assertEqual(assess(self.root, baseline=None, approval=None, evidence={'regression':{} })['gates']['evidence']['status'], 'FAIL')
    def test_evidence_manifest_mismatch(self):
        ev = {'regression': {'successful': True, 'tests_run': 1, 'stage_test_files': {}}, 'manifest': {'files':{}}}
        self.assertEqual(assess(self.root, baseline=None, approval=None, evidence=ev)['gates']['evidence']['status'], 'FAIL')
    def test_boolean_test_count_fails(self):
        ev = {'regression': {'successful': True, 'tests_run': True}}
        self.assertEqual(assess(self.root, baseline=None, approval=None, evidence=ev)['gates']['evidence']['status'], 'FAIL')
