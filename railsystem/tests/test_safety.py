import copy
import unittest
from pathlib import Path
from railsystem.architecture import load_registry
from railsystem.requirements import load_requirements
from railsystem.safety import load_hazards, validate_hazards, safety_report, SafetyError

ROOT=Path(__file__).resolve().parents[1]
class TestSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arch=load_registry(ROOT/'architecture/registry.json')
        cls.reqs=load_requirements(ROOT/'requirements/registry.json',cls.arch)
        cls.log=load_hazards(ROOT/'safety/hazards.json',cls.arch,cls.reqs)
    def check_invalid(self,change):
        data=copy.deepcopy(self.log)
        change(data['hazards'][0])
        with self.assertRaises(SafetyError):validate_hazards(data,self.arch,self.reqs)
    def test_valid(self):self.assertTrue(validate_hazards(self.log,self.arch,self.reqs))
    def test_report(self):
        r=safety_report(self.log,self.arch,self.reqs)
        self.assertEqual(r['total'],6)
        self.assertEqual(r['closed'],0)
        self.assertFalse(r['operational_go'])
    def test_duplicate_id(self):self.check_invalid(lambda h:h.update(id='RAIL-HAZ-0002'))
    def test_unknown_component(self):self.check_invalid(lambda h:h.update(component='nonexistent'))
    def test_unknown_requirement(self):self.check_invalid(lambda h:h.update(requirement_ids=['RAIL-REQ-9999']))
    def test_requires_safety_link(self):self.check_invalid(lambda h:h.update(requirement_ids=['RAIL-REQ-0006']))
    def test_no_controls(self):self.check_invalid(lambda h:h.update(controls=[]))
    def test_no_closure(self):self.check_invalid(lambda h:h.update(status='closed'))
    def test_no_mitigated(self):self.check_invalid(lambda h:h.update(status='mitigated'))
    def test_no_authorization(self):self.check_invalid(lambda h:h.update(operational_authorization=True))
    def test_no_unreviewed_evidence(self):self.check_invalid(lambda h:h.update(closure_evidence=['report.pdf']))
    def test_unknown_likelihood(self):self.check_invalid(lambda h:h.update(likelihood='certain'))
    def test_missing_owner(self):self.check_invalid(lambda h:h.update(owner_role=''))
    def test_duplicate_controls(self):self.check_invalid(lambda h:h.update(controls=['same','same']))
    def test_empty_registry(self):
        data=copy.deepcopy(self.log);data['hazards']=[]
        with self.assertRaises(SafetyError):validate_hazards(data,self.arch,self.reqs)
