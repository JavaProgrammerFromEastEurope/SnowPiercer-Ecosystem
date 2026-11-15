import os
import tempfile
import threading
import unittest
from pathlib import Path
from ai_cognition import ReplayStore, RotationManager, RecoveryRequired, TrustedAdmission, signed_envelope, AdmissionRejected

K1 = b'a'*32
K2 = b'b'*32
OBS = {'event_id':'evt001','source':'trainos','severity':'warning','description':'ok'}

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dbpath = str(Path(self.tmp.name)/'db.sqlite')
        self.store = ReplayStore(self.dbpath)
        self.addCleanup(self.store.close)
        self.anchor = str(Path(self.tmp.name)/'anchor')
        self.m = RotationManager(self.store, self.anchor, {'trainos':K1}, bootstrap=True)
        self.m.provision('trainos')

    def test_normal_rotation_and_replay_persists(self):
        self.m.admit(signed_envelope(OBS,1000,'a'*16,K1),clock=lambda:1000)
        self.m.rotate('trainos',K2)
        with self.assertRaises(AdmissionRejected):
            self.m.admit(signed_envelope(OBS,1000,'a'*16,K2),clock=lambda:1000)
        obs=dict(OBS,event_id='evt002')
        self.assertFalse(self.m.admit(signed_envelope(obs,1000,'b'*16,K2),clock=lambda:1000).actionable)

    def test_prepared_crash_fences_legacy_and_recover(self):
        with self.assertRaises(RuntimeError): self.m.rotate('trainos',K2,fault='prepared')
        with self.assertRaises(AdmissionRejected):
            TrustedAdmission({'trainos':K1},self.store,clock=lambda:1000).admit(signed_envelope(OBS,1000,'c'*16,K1))
        with self.assertRaises(RecoveryRequired): self.m.recover('trainos',K1)
        self.m.recover('trainos',K1,approved=True)
        self.m.admit(signed_envelope(OBS,1000,'c'*16,K1),clock=lambda:1000)

    def test_committed_crash_requires_external_reconciliation(self):
        with self.assertRaises(RuntimeError): self.m.rotate('trainos',K2,fault='committed')
        with self.assertRaises(RecoveryRequired): self.m.recover('trainos',K2,approved=True)
        with self.assertRaises(AdmissionRejected):
            TrustedAdmission({'trainos':K1},self.store,clock=lambda:1000).admit(signed_envelope(OBS,1000,'d'*16,K1))

    def test_anchored_crash_recover(self):
        with self.assertRaises(RuntimeError): self.m.rotate('trainos',K2,fault='anchored')
        with self.assertRaises(RecoveryRequired): self.m.recover('trainos',K1,approved=True)
        self.m.recover('trainos',K2,approved=True)
        self.m.admit(signed_envelope(OBS,1000,'e'*16,K2),clock=lambda:1000)

    def test_anchor_rollback_and_missing_fence(self):
        self.m.rotate('trainos',K2)
        Path(self.anchor).write_text('0\n')
        with self.assertRaises(RecoveryRequired): self.m._check()
        with self.assertRaises(AdmissionRejected):
            TrustedAdmission({'trainos':K2},self.store,clock=lambda:1000).admit(signed_envelope(OBS,1000,'f'*16,K2))
        os.unlink(self.anchor)
        with self.assertRaises(RecoveryRequired): self.m._check()

    def test_reopen_after_crash(self):
        with self.assertRaises(RuntimeError): self.m.rotate('trainos',K2,fault='prepared')
        second=ReplayStore(self.dbpath)
        self.addCleanup(second.close)
        with self.assertRaises(RecoveryRequired): RotationManager(second,self.anchor,{'trainos':K1})

    def test_concurrent_duplicate_reservation(self):
        outcomes=[]
        def run():
            try: self.m.admit(signed_envelope(OBS,1000,'g'*16,K1),clock=lambda:1000); outcomes.append('ok')
            except AdmissionRejected: outcomes.append('rejected')
        threads=[threading.Thread(target=run) for _ in range(8)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(outcomes.count('ok'),1)
        self.assertEqual(outcomes.count('rejected'),7)

    def test_no_anchor_reprovision(self):
        with self.assertRaises(RecoveryRequired):self.m.initialize_anchor()

if __name__=='__main__':unittest.main()
