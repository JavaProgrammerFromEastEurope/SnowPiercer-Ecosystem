import os
import tempfile
import unittest
from pathlib import Path
from snowpiercer_logistics.stage010 import IsolationPolicy
from snowpiercer_logistics.stage011 import DeploymentLayout
from snowpiercer_logistics.stage012 import DeploymentPlan, require_production_entrypoint
from snowpiercer_logistics.secure import AdmissionError

class Stage012Tests(unittest.TestCase):
    def make_plan(self, base):
        p = IsolationPolicy(31001, 31002, 31003, (31004,))
        roots = [str(Path(base)/x) for x in ('service','witness','authority')]
        layout = DeploymentLayout(p, *roots, *(str(Path(r)/'ipc.sock') for r in roots))
        return DeploymentPlan(layout)
    def test_valid_plan(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(len(self.make_plan(d).installation_steps()),3)
    def test_duplicate_uid_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            plan=self.make_plan(d)
            object.__setattr__(plan.layout, 'policy', IsolationPolicy(31001,31001,31003,(31004,)))
            with self.assertRaises(AdmissionError): plan.validate()
    def test_bad_socket_location_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            plan=self.make_plan(d)
            object.__setattr__(plan.layout,'service_socket',str(Path(d)/'untrusted.sock'))
            with self.assertRaises(AdmissionError): plan.validate()
    def test_production_entrypoint_denies_missing_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            plan=self.make_plan(d)
            with self.assertRaises(AdmissionError):
                require_production_entrypoint(plan.layout, acceptance_file=str(Path(d)/'missing'))
