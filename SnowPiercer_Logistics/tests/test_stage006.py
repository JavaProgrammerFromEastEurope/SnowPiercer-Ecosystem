import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from snowpiercer_logistics.stage006 import recover_after_witness_cas
from snowpiercer_logistics.secure import AdmissionError
from snowpiercer_logistics.witness import WitnessAuthority, witness_request
from snowpiercer_logistics.production import WitnessBackedLogisticsService

class Stage006Tests(unittest.TestCase):
    def test_consumed_permit_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'service'
            root.mkdir(mode=0o700)
            token='a'*64
            digest=hashlib.sha256(token.encode()).hexdigest()
            with self.assertRaises(AdmissionError):
                recover_after_witness_cas(root, '/nonexistent', permit=token, uid=os.geteuid(),permit_digest=digest)
            with self.assertRaisesRegex(AdmissionError, 'replayed'):
                recover_after_witness_cas(root, '/nonexistent', permit=token, uid=os.geteuid(),permit_digest=digest)
    def test_uid_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(AdmissionError,'UID mismatch'):
                recover_after_witness_cas(tmp,'/nonexistent',permit='a'*64,uid=os.geteuid()+1,permit_digest=hashlib.sha256(b'a'*64).hexdigest())
    def test_witness_cas_and_service_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            with WitnessAuthority(base/'witness',os.geteuid()) as witness:
                with WitnessBackedLogisticsService(base/'service',{os.geteuid():'admin'},witness.socket_path):
                    pass
                self.assertEqual(witness_request(witness.socket_path,'read')['events'],0)
    def test_reject_untrusted_witness_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            with WitnessAuthority(base/'witness',os.geteuid()) as witness:
                with WitnessBackedLogisticsService(base/'service',{os.geteuid():'admin'},witness.socket_path):
                    pass
                (base/'witness'/'monotonic.json').unlink()
                with self.assertRaises(AdmissionError):
                    WitnessBackedLogisticsService(base/'service',{os.geteuid():'admin'},witness.socket_path).start()

if __name__=='__main__': unittest.main()
