from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from subsystems.operations.ops_core import (InventoryError, MODULE_IDS, assess,
    artifact_observation, dependency_cycles, load_json, safe_artifact, validate_catalog, write_report)

ROOT = Path(__file__).resolve().parents[3]
CATALOG = load_json(ROOT / 'subsystems/operations/config/catalog.json')


class CatalogTests(unittest.TestCase):
    def test_exact_nine_modules(self):
        validate_catalog(CATALOG)
        self.assertEqual(MODULE_IDS, {m['moduleId'] for m in CATALOG['modules']})

    def test_duplicate_and_missing_modules_rejected(self):
        for malformed in ('duplicate', 'missing'):
            with self.subTest(malformed=malformed):
                data = copy.deepcopy(CATALOG)
                if malformed == 'duplicate':
                    data['modules'][0] = copy.deepcopy(data['modules'][1])
                else:
                    data['modules'].pop()
                with self.assertRaises(InventoryError):
                    validate_catalog(data)

    def test_mandatory_global_blockers_cannot_be_silently_removed_or_marked_passed(self):
        for mode in ('remove','duplicate','pass'):
            data = copy.deepcopy(CATALOG)
            if mode == 'remove':
                data['globalBlockers'].pop()
            elif mode == 'duplicate':
                data['globalBlockers'][0] = copy.deepcopy(data['globalBlockers'][1])
            else:
                data['globalBlockers'][0]['state'] = 'VERIFIED'
            with self.subTest(mode=mode), self.assertRaises(InventoryError):
                validate_catalog(data)

    def test_fake_go_cannot_enter_catalog(self):
        data = copy.deepcopy(CATALOG)
        data['modules'][0]['readiness'] = 'GO'
        with self.assertRaises(InventoryError):
            validate_catalog(data)

    def test_unknown_dependency_rejected(self):
        data = copy.deepcopy(CATALOG)
        data['modules'][0]['dependencies'].append('SP-FAKE')
        with self.assertRaises(InventoryError):
            validate_catalog(data)

    def test_duplicate_artifact_rejected(self):
        data = copy.deepcopy(CATALOG)
        data['modules'][0]['artifacts'].append(copy.deepcopy(data['modules'][0]['artifacts'][0]))
        with self.assertRaises(InventoryError):
            validate_catalog(data)

    def test_bad_digest_rejected(self):
        data = copy.deepcopy(CATALOG)
        data['modules'][0]['artifacts'][0]['expectedSha256'] = 'f'*63
        with self.assertRaises(InventoryError):
            validate_catalog(data)

    def test_security_operations_dependency_cycle_explicit(self):
        cycles = dependency_cycles(CATALOG['modules'])
        self.assertTrue(any('SP-OPS' in c and 'SP-SAFE' in c for c in cycles))

    def test_acyclic_graph(self):
        self.assertEqual([], dependency_cycles([
            {'moduleId':'x','dependencies':['y']},
            {'moduleId':'y','dependencies':[]}]))


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'evidence').mkdir()
        (self.root / 'evidence/trace.json').write_bytes(b'{"test":true}\n')

    def test_regular_file_digest_match_is_unattested(self):
        sha = hashlib.sha256(b'{"test":true}\n').hexdigest()
        observed = artifact_observation(self.root, {
            'path': 'evidence/trace.json', 'expectedSha256': sha,
            'classification':'LOCAL_OBSERVATION'})
        self.assertEqual('DIGEST_MATCH_UNATTESTED', observed['status'])

    def test_digest_mismatch_fails(self):
        observed = artifact_observation(self.root, {
            'path': 'evidence/trace.json', 'expectedSha256': '0'*64,
            'classification':'LOCAL_OBSERVATION'})
        self.assertEqual('DIGEST_MISMATCH', observed['status'])

    def test_relative_unsafe_paths_rejected(self):
        for path in ('../bad', '/etc/passwd', 'evidence/../trace.json', './evidence/trace.json',
                     'evidence//trace.json', 'evidence\\trace.json', 'evidence/trace.json\x00'):
            with self.subTest(path=path), self.assertRaises(InventoryError):
                safe_artifact(self.root, path)

    def test_missing_is_not_pass(self):
        observed = artifact_observation(self.root, {
            'path':'evidence/missing.json','classification':'LOCAL_OBSERVATION'})
        self.assertEqual('UNAVAILABLE_OR_UNSAFE', observed['status'])

    def test_symlinks_rejected(self):
        (self.root / 'evidence/link.json').symlink_to(self.root/'evidence/trace.json')
        with self.assertRaises(InventoryError):
            safe_artifact(self.root,'evidence/link.json')
        (self.root / 'alias').symlink_to(self.root/'evidence', target_is_directory=True)
        with self.assertRaises(InventoryError):
            safe_artifact(self.root,'alias/trace.json')

    def test_directories_rejected(self):
        with self.assertRaises(InventoryError):
            safe_artifact(self.root, 'evidence')

    def test_no_go_even_without_global_failure(self):
        report = assess(self.root, CATALOG, at='2026-11-15T00:00:00+00:00')
        self.assertEqual('NO_GO', report['decision'])
        self.assertIs(report['operationalReady'], False)
        self.assertIsNone(report['ecosystemCompletionPercent'])
        self.assertEqual(9, len(report['modules']))
        self.assertGreater(report['summary']['artifactFailures'], 0)

    def test_empty_controls_block(self):
        altered = copy.deepcopy(CATALOG)
        altered['globalBlockers'] = []
        with self.assertRaises(InventoryError):
            assess(self.root, altered)

    def test_atomic_report_output(self):
        dest = self.root/'report.json'
        write_report({'decision':'NO_GO'}, dest)
        self.assertEqual('NO_GO', json.loads(dest.read_text())['decision'])
        self.assertEqual([], list(self.root.glob('*.tmp-*')))


if __name__ == '__main__':
    unittest.main()
