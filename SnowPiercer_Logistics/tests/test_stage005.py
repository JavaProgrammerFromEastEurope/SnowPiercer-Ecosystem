import os
import tempfile
import unittest
from pathlib import Path
from snowpiercer_logistics.witness import WitnessAuthority, witness_request
from snowpiercer_logistics.production import WitnessBackedLogisticsService
from snowpiercer_logistics.secure import AdmissionError, request

class WitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.witness=WitnessAuthority(self.base/'witness',os.getuid()).start()
        self.addCleanup(self.witness.stop)
    def test_cas_monotonic_replay_and_genesis(self):
        path=self.witness.socket_path
        genesis={'events':0,'head_hash':'0'*64}
        self.assertIsNone(witness_request(path,'read'))
        self.assertEqual(witness_request(path,'cas',before=None,after=genesis),genesis)
        with self.assertRaises(AdmissionError): witness_request(path,'cas',before=None,after=genesis)
        with self.assertRaises(AdmissionError): witness_request(path,'cas',before=genesis,after=genesis)
        successor={'events':1,'head_hash':'1'*64}
        self.assertEqual(witness_request(path,'cas',before=genesis,after=successor),successor)
        with self.assertRaises(AdmissionError): witness_request(path,'cas',before=successor,after=genesis)
    def test_uid_rejection(self):
        self.witness.stop()
        witness=WitnessAuthority(self.base/'other',os.getuid()+10000).start()
        self.addCleanup(witness.stop)
        with self.assertRaises(AdmissionError): witness_request(witness.socket_path,'read')
    def test_service_genesis_and_reopen(self):
        root=self.base/'service'
        with WitnessBackedLogisticsService(root,{os.getuid():'admin'},self.witness.socket_path) as service:
            self.assertTrue(request(service.socket_path,'verify')['ok'])
        with WitnessBackedLogisticsService(root,{os.getuid():'admin'},self.witness.socket_path) as service:
            self.assertTrue(request(service.socket_path,'verify')['ok'])
    def test_checkpoint_rollback_rejected(self):
        root=self.base/'service'
        with WitnessBackedLogisticsService(root,{os.getuid():'admin'},self.witness.socket_path): pass
        (root/'checkpoint.json').unlink()
        with self.assertRaises(AdmissionError): WitnessBackedLogisticsService(root,{os.getuid():'admin'},self.witness.socket_path).start()
    def test_witness_unavailable_fails_closed(self):
        self.witness.stop()
        with self.assertRaises((OSError,AdmissionError)):
            WitnessBackedLogisticsService(self.base/'service',{os.getuid():'admin'},self.witness.socket_path).start()

if __name__=='__main__': unittest.main()
