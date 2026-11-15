import os
import tempfile
import unittest
from pathlib import Path
from snowpiercer_logistics.stage008 import MandatoryAdmissionLogisticsService
from snowpiercer_logistics.permit_authority import RecoveryPermitAuthority, permit_request
from snowpiercer_logistics.witness import WitnessAuthority
from snowpiercer_logistics.secure import AdmissionError, request

class Stage008(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.uid = os.getuid()

    def test_missing_permit_authority_fails_closed(self):
        with WitnessAuthority(self.base/'w', self.uid) as w:
            svc = MandatoryAdmissionLogisticsService(self.base/'s', {self.uid:'admin'}, w.socket_path, self.base/'absent.sock')
            with self.assertRaises(AdmissionError): svc.start()

    def test_broker_permit_is_one_time_through_service_ipc(self):
        with WitnessAuthority(self.base/'w', self.uid) as w:
            with RecoveryPermitAuthority(self.base/'p', self.uid, self.uid) as p:
                with MandatoryAdmissionLogisticsService(self.base/'s', {self.uid:'admin'}, w.socket_path, p.socket_path) as svc:
                    self.assertFalse(request(svc.socket_path,'issue_permit',{'uid':self.uid})['ok'])
                    token = permit_request(p.socket_path,'issue',scope='logistics-recovery',target_uid=self.uid)['permit']
                    self.assertTrue(request(svc.socket_path,'recover',{'permit':token})['ok'])
                    self.assertFalse(request(svc.socket_path,'recover',{'permit':token})['ok'])

    def test_wrong_scope_is_denied(self):
        with WitnessAuthority(self.base/'w', self.uid) as w:
            with RecoveryPermitAuthority(self.base/'p', self.uid, self.uid) as p:
                with MandatoryAdmissionLogisticsService(self.base/'s', {self.uid:'admin'}, w.socket_path, p.socket_path) as svc:
                    token = permit_request(p.socket_path,'issue',scope='other',target_uid=self.uid)['permit']
                    self.assertFalse(request(svc.socket_path,'recover',{'permit':token})['ok'])
