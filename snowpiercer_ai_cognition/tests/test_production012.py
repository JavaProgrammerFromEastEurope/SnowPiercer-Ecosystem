import tempfile
import unittest
from pathlib import Path
from ai_cognition import (ReplayStore, IndependentAnchor, HardenedRotationManager,
    AnchoredAdmissionGateway, AuditCheckpoint, RecoveryRequired, signed_envelope)
from ai_cognition.production012 import DurableRecoveryAuthorizer, ProductionAdmissionIPCServer
from ai_cognition.isolation import recovery_permit
K=b'a'*32; ROOT=b'b'*32; AUTH=b'c'*32; AUDIT=b'd'*32; CHECK=b'e'*32
OBS={'event_id':'event001','source':'trainos','severity':'warning','description':'ok'}
class Production012Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.store=ReplayStore(str(self.root/'db')); self.addCleanup(self.store.close)
        manager=HardenedRotationManager(self.store,str(self.root/'legacy'),{'trainos':K},independent_anchor=IndependentAnchor(self.root/'independent',ROOT),recovery_secret=AUTH,bootstrap=True)
        manager.provision('trainos')
        self.gw=AnchoredAdmissionGateway(manager,AUDIT,checkpoint=AuditCheckpoint(self.root/'checkpoint',CHECK),clock=lambda:1000,bootstrap=True)
    def envelope(self,nonce='a'*16): return signed_envelope(OBS,1000,nonce,K)
    def permit(self,id='abcdefgh'): return recovery_permit(AUTH,id,0,'0'*64)
    def test_production_requires_anchor(self):
        with self.assertRaises(RecoveryRequired):
            ProductionAdmissionIPCServer(object(),self.root/'sock',allowed_uids=[1],recovery_secret=AUTH)
    def test_bootstrap_verify_and_fence(self):
        service=ProductionAdmissionIPCServer(self.gw,self.root/'sock',allowed_uids=[1],recovery_secret=AUTH)
        self.assertEqual(service.gateway.verify()[0],0)
        with self.assertRaises(RuntimeError): self.gw.admit(self.envelope(),fault='after_commit')
        with self.assertRaises(RecoveryRequired):
            ProductionAdmissionIPCServer(self.gw,self.root/'sock',allowed_uids=[1],recovery_secret=AUTH)
    def test_durable_permit_one_time(self):
        auth=DurableRecoveryAuthorizer(self.gw,AUTH)
        with self.assertRaises(RuntimeError): self.gw.admit(self.envelope(),fault='after_commit')
        self.assertEqual(auth.reconcile(self.permit())[0],1)
        with self.assertRaises(RecoveryRequired): auth.reconcile(self.permit())
        self.assertEqual(self.store._db.execute('SELECT count(*) FROM production_recovery_permits').fetchone()[0],1)
    def test_invalid_mac_never_consumed(self):
        auth=DurableRecoveryAuthorizer(self.gw,AUTH)
        with self.assertRaises(RuntimeError): self.gw.admit(self.envelope(),fault='after_commit')
        p=self.permit(); p['mac']='0'*64
        with self.assertRaises(RecoveryRequired): auth.reconcile(p)
        self.assertEqual(self.store._db.execute('SELECT count(*) FROM production_recovery_permits').fetchone()[0],0)
    def test_replay_after_simulated_crash_before_checkpoint(self):
        auth=DurableRecoveryAuthorizer(self.gw,AUTH)
        with self.assertRaises(RuntimeError): self.gw.admit(self.envelope(),fault='after_commit')
        original=self.gw.reconcile
        def crash(*args,**kwargs): raise RuntimeError('SIGKILL boundary simulation')
        self.gw.reconcile=crash
        with self.assertRaises(RuntimeError): auth.reconcile(self.permit())
        self.gw.reconcile=original
        auth2=DurableRecoveryAuthorizer(self.gw,AUTH)
        with self.assertRaisesRegex(RecoveryRequired,'RECOVERY_PERMIT_REPLAY'):
            auth2.reconcile(self.permit())
        self.assertEqual(auth2.reconcile(self.permit('ijklmnop'))[0],1)
    def test_recovery_refuses_multiple_unanchored(self):
        auth=DurableRecoveryAuthorizer(self.gw,AUTH)
        with self.assertRaises(RecoveryRequired): auth.reconcile(self.permit())
        self.assertEqual(self.store._db.execute('SELECT count(*) FROM production_recovery_permits').fetchone()[0],0)
    def test_checkpoint_corruption_blocks_production(self):
        self.gw.checkpoint.path.write_text('tamper')
        with self.assertRaises(RecoveryRequired):
            ProductionAdmissionIPCServer(self.gw,self.root/'sock',allowed_uids=[1],recovery_secret=AUTH)
