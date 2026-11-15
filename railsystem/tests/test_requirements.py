import copy
import unittest
from pathlib import Path
from railsystem.architecture import load_registry
from railsystem.requirements import RequirementsError, load_requirements, validate_requirements, traceability_report
ROOT = Path(__file__).resolve().parents[1]
class RequirementsTests(unittest.TestCase):
    def setUp(self):
        self.arch = load_registry(ROOT/'architecture'/'registry.json')
        self.data = load_requirements(ROOT/'requirements'/'registry.json', self.arch)
    def reject(self):
        with self.assertRaises(RequirementsError): validate_requirements(self.data,self.arch)
    def test_valid(self): self.assertTrue(validate_requirements(self.data,self.arch))
    def test_twelve_requirements(self): self.assertEqual(len(self.data['requirements']),12)
    def test_all_components_covered(self): self.assertFalse(traceability_report(self.data,self.arch)['uncovered_components'])
    def test_none_verified(self): self.assertEqual(traceability_report(self.data,self.arch)['verified'],0)
    def test_duplicate_id(self):
        self.data['requirements'].append(copy.deepcopy(self.data['requirements'][0])); self.reject()
    def test_bad_id(self):
        self.data['requirements'][0]['id']='INVALID'; self.reject()
    def test_unknown_component(self):
        self.data['requirements'][0]['component']='unknown'; self.reject()
    def test_blank_statement(self):
        self.data['requirements'][0]['statement']=' '; self.reject()
    def test_invalid_priority(self):
        self.data['requirements'][0]['priority']='urgent'; self.reject()
    def test_invalid_method(self):
        self.data['requirements'][0]['verification_method']='guess'; self.reject()
    def test_invalid_stage(self):
        self.data['requirements'][0]['planned_stage']='tomorrow'; self.reject()
    def test_verified_without_evidence(self):
        self.data['requirements'][0]['status']='verified'; self.reject()
    def test_unverified_with_evidence(self):
        self.data['requirements'][0]['verification_evidence']=['test:123']; self.reject()
    def test_verified_with_evidence(self):
        self.data['requirements'][0]['status']='verified'
        self.data['requirements'][0]['verification_evidence']=['test:123']
        self.assertTrue(validate_requirements(self.data,self.arch))
    def test_duplicate_evidence(self):
        self.data['requirements'][0]['status']='verified'
        self.data['requirements'][0]['verification_evidence']=['test:123','test:123']; self.reject()
    def test_invalid_schema(self):
        self.data['schema_version']='2.0'; self.reject()
