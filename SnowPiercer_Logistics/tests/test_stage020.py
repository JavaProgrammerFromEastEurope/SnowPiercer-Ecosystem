import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from snowpiercer_logistics.secure import AdmissionError
from snowpiercer_logistics.stage020 import (ProductionIdentityPolicy,verify_endpoint,
    MandatoryProductionLogisticsService,crash_state_matrix,production_admission)

class Stage020Tests(unittest.TestCase):
    def test_uid_policy(self):
        with self.assertRaises(AdmissionError):
            ProductionIdentityPolicy(12001,12001,12003,12004).validate()
        with self.assertRaises(AdmissionError):
            ProductionIdentityPolicy(0,12002,12003,12004).validate()
        with patch('snowpiercer_logistics.stage020.os.geteuid',return_value=12001):
            with patch('snowpiercer_logistics.stage020.socket.SO_PEERCRED',new=17,create=True):
                ProductionIdentityPolicy(12001,12002,12003,12004).validate()
    def test_endpoint_owner_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sock'
            with socket.socket(socket.AF_UNIX) as s:
                s.bind(str(p)); os.chmod(p,0o600)
                self.assertEqual(len(verify_endpoint(p,os.geteuid())),2)
                with self.assertRaises(AdmissionError): verify_endpoint(p,os.geteuid()+1)
                q=Path(d)/'alias'; q.symlink_to(p)
                with self.assertRaises(AdmissionError): verify_endpoint(q,os.geteuid())
                os.chmod(p,0o666)
                with self.assertRaises(AdmissionError): verify_endpoint(p,os.geteuid())
    def test_crash_classification(self):
        a={'events':0,'head_hash':'a'*64}
        result=crash_state_matrix(a)
        self.assertEqual(result['stable'],'COMMITTED')
        for name,state in result.items():
            if name!='stable': self.assertTrue(state.startswith('QUARANTINED_'),(name,state))
    def test_production_closed(self):
        with self.assertRaises(AdmissionError): production_admission()
        with self.assertRaises(AdmissionError):
            MandatoryProductionLogisticsService.start(object.__new__(MandatoryProductionLogisticsService))
