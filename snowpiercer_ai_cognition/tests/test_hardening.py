import tempfile
import threading
import unittest
from pathlib import Path
from ai_cognition import (ReplayStore, IndependentAnchor, HardenedRotationManager,
                          RecoveryRequired, TrustedAdmission, signed_envelope, AdmissionRejected)
K1=b'a'*32; K2=b'b'*32; ROOT=b'c'*32; AUTH=b'd'*32
OBS={'event_id':'evt001','source':'trainos','severity':'warning','description':'ok'}

class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.store=ReplayStore(str(root/'replay.db')); self.addCleanup(self.store.close)
        self.anchor=IndependentAnchor(root/'independent',ROOT)
        self.manager=HardenedRotationManager(self.store,str(root/'legacy'),{'trainos':K1},independent_anchor=self.anchor,recovery_secret=AUTH,bootstrap=True)
        self.manager.provision('trainos')
    def test_rotate_and_legacy_old_key_rejected(self):
        self.manager.rotate('trainos',K2)
        legacy=TrustedAdmission({'trainos':K1},self.store,clock=lambda:1000)
        with self.assertRaisesRegex(AdmissionRejected,'LEGACY_KEY_RETIRED'):
            legacy.admit(signed_envelope(OBS,1000,'a'*16,K1))
        self.manager.admit(signed_envelope(OBS,1000,'b'*16,K2),clock=lambda:1000)
    def test_independent_anchor_tamper(self):
        self.anchor.path.write_text('{"epoch":0,"mac":"fake"}')
        with self.assertRaises(RecoveryRequired): self.manager._check()
    def test_independent_anchor_rollback(self):
        old=self.anchor.path.read_bytes(); self.manager.rotate('trainos',K2)
        self.anchor.path.write_bytes(old)
        with self.assertRaisesRegex(RecoveryRequired,'INDEPENDENT_ANCHOR_MISMATCH'): self.manager._check()
    def test_recovery_signed_token(self):
        with self.assertRaises(RuntimeError): self.manager.rotate('trainos',K2,fault='prepared')
        with self.assertRaises(RecoveryRequired): self.manager.recover('trainos',K1,approved=True)
        token=self.manager.recovery_token('trainos',K1,'token-unique-0001')
        with self.assertRaises(RecoveryRequired): self.manager.recover('trainos',K1,token_id='token-unique-0001',authorization='0'*64)
        self.manager.recover('trainos',K1,token_id='token-unique-0001',authorization=token)
        with self.assertRaises(RecoveryRequired): self.manager.recover('trainos',K1,token_id='token-unique-0001',authorization=token)
    def test_crash_after_independent_anchor_fences(self):
        with self.assertRaises(RuntimeError): self.manager.rotate('trainos',K2,fault='anchored')
        token=self.manager.recovery_token('trainos',K2,'token-unique-0002')
        self.manager.recover('trainos',K2,token_id='token-unique-0002',authorization=token)
    def test_crash_after_commit_fails_closed(self):
        with self.assertRaises(RuntimeError): self.manager.rotate('trainos',K2,fault='committed')
        with self.assertRaises(RecoveryRequired): self.manager._check()
    def test_concurrent_recovery_single_winner(self):
        with self.assertRaises(RuntimeError): self.manager.rotate('trainos',K2,fault='prepared')
        token=self.manager.recovery_token('trainos',K1,'token-unique-0003')
        results=[]
        def work():
            try: self.manager.recover('trainos',K1,token_id='token-unique-0003',authorization=token); results.append('ok')
            except RecoveryRequired: results.append('reject')
        threads=[threading.Thread(target=work) for _ in range(5)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(results.count('ok'),1)
    def test_missing_independent_anchor(self):
        self.anchor.path.unlink()
        with self.assertRaises(RecoveryRequired): self.manager._check()

if __name__=='__main__': unittest.main()
