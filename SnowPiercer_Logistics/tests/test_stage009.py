import os
import tempfile
import unittest
from pathlib import Path
from snowpiercer_logistics.stage009 import ClientBoundPermitAuthority, ClientBoundLogisticsService, client_permit_request
from snowpiercer_logistics.witness import WitnessAuthority
from snowpiercer_logistics.secure import request, AdmissionError

class Stage009(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.uid = os.getuid()

    def test_client_uid_bound_replay_and_legacy_denial(self):
        with WitnessAuthority(self.base/'w',self.uid) as w:
            with ClientBoundPermitAuthority(self.base/'p',self.uid,self.uid) as p:
                with ClientBoundLogisticsService(self.base/'s',{self.uid:'admin'},w.socket_path,p.socket_path) as s:
                    token=client_permit_request(p.socket_path,'issue_client',scope='logistics-recovery',client_uid=self.uid)['permit']
                    self.assertTrue(request(s.socket_path,'recover',{'permit':token})['ok'])
                    self.assertFalse(request(s.socket_path,'recover',{'permit':token})['ok'])
                    self.assertFalse(request(s.socket_path,'issue_permit',{'uid':self.uid})['ok'])
                    with self.assertRaises(AdmissionError):
                        client_permit_request(p.socket_path,'consume',scope='logistics-recovery',client_uid=self.uid,permit=token)

    def test_wrong_client_uid_does_not_consume(self):
        with WitnessAuthority(self.base/'w',self.uid) as w:
            with ClientBoundPermitAuthority(self.base/'p',self.uid,self.uid) as p:
                with ClientBoundLogisticsService(self.base/'s',{self.uid:'admin'},w.socket_path,p.socket_path) as s:
                    token=client_permit_request(p.socket_path,'issue_client',scope='logistics-recovery',client_uid=self.uid+1)['permit']
                    self.assertFalse(request(s.socket_path,'recover',{'permit':token})['ok'])
                    with self.assertRaises(AdmissionError):
                        client_permit_request(p.socket_path,'consume_client',scope='logistics-recovery',client_uid=self.uid,permit=token)
                    self.assertTrue(client_permit_request(p.socket_path,'consume_client',scope='logistics-recovery',client_uid=self.uid+1,permit=token)['consumed'])

    def test_consumption_survives_restart(self):
        with ClientBoundPermitAuthority(self.base/'p',self.uid,self.uid) as p:
            token=client_permit_request(p.socket_path,'issue_client',scope='x',client_uid=self.uid)['permit']
            client_permit_request(p.socket_path,'consume_client',scope='x',client_uid=self.uid,permit=token)
        with ClientBoundPermitAuthority(self.base/'p',self.uid,self.uid) as p:
            with self.assertRaises(AdmissionError):
                client_permit_request(p.socket_path,'consume_client',scope='x',client_uid=self.uid,permit=token)

    def test_auditor_recovery_denied(self):
        with WitnessAuthority(self.base/'w',self.uid) as w:
            with ClientBoundPermitAuthority(self.base/'p',self.uid,self.uid) as p:
                with ClientBoundLogisticsService(self.base/'s',{self.uid:'auditor'},w.socket_path,p.socket_path) as s:
                    token=client_permit_request(p.socket_path,'issue_client',scope='logistics-recovery',client_uid=self.uid)['permit']
                    self.assertFalse(request(s.socket_path,'recover',{'permit':token})['ok'])
