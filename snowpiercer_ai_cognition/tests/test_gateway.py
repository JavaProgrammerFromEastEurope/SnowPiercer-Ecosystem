import contextlib
import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path
from ai_cognition import (ReplayStore, IndependentAnchor, HardenedRotationManager,
                          MandatoryAdmissionGateway, RecoveryRequired, AdmissionRejected, signed_envelope)
K=b'a'*32; ROOT=b'b'*32; AUTH=b'c'*32; AUDIT=b'd'*32
OBS={'event_id':'event001','source':'trainos','severity':'warning','description':'ok'}
class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name); self.path=str(root/'db')
        self.store=ReplayStore(self.path); self.addCleanup(self.store.close)
        self.manager=HardenedRotationManager(self.store,str(root/'legacy'),{'trainos':K},independent_anchor=IndependentAnchor(root/'independent',ROOT),recovery_secret=AUTH,bootstrap=True)
        self.manager.provision('trainos')
        self.gateway=MandatoryAdmissionGateway(self.manager,AUDIT,clock=lambda:1000,bootstrap=True)
    def env(self,nonce='a'*16,event='event001'):
        return signed_envelope(dict(OBS,event_id=event),1000,nonce,K)
    def test_admit_and_audit(self):
        self.assertFalse(self.gateway.admit(self.env()).actionable)
        self.assertEqual(self.gateway.verify()[0],1)
    def test_replay(self):
        self.gateway.admit(self.env())
        with self.assertRaisesRegex(AdmissionRejected,'REPLAY_DETECTED'): self.gateway.admit(self.env())
    def test_legacy_reserve_blocked(self):
        with self.assertRaises(AdmissionRejected): self.store.reserve('trainos','a'*16,'event001',1000)
    def test_external_connection_blocked(self):
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            with self.assertRaises(sqlite3.DatabaseError): db.execute('INSERT INTO seen VALUES (?,?,?,?)',('trainos','a'*16,'event001',1000))
    def test_faults_atomic(self):
        for fault in ('before_insert','after_insert','after_audit'):
            with self.assertRaises(RuntimeError): self.gateway.admit(self.env(),fault=fault)
            self.assertEqual(self.gateway.verify()[0],0)
        self.gateway.admit(self.env())
    def test_audit_tamper(self):
        self.gateway.admit(self.env())
        self.store._db.execute('DROP TRIGGER gateway_audit_update')
        self.store._db.execute("UPDATE gateway_audit SET event='FORGED'")
        with self.assertRaises(RecoveryRequired): self.gateway.verify()
    def test_anchor_rollback(self):
        self.manager.independent_anchor.path.write_text('tampered')
        with self.assertRaises(RecoveryRequired): self.gateway.admit(self.env())
    def test_concurrent_single_winner(self):
        def attempt(_):
            try: self.gateway.admit(self.env()); return True
            except AdmissionRejected: return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(attempt,range(6)))
        self.assertEqual(sum(results),1)
    def test_reopen_existing_gateway(self):
        self.gateway.admit(self.env())
        another=MandatoryAdmissionGateway(self.manager,AUDIT,clock=lambda:1000)
        self.assertEqual(another.verify()[0],1)
    def test_invalid_signature(self):
        env=self.env(); env['mac']='0'*64
        with self.assertRaisesRegex(AdmissionRejected,'AUTHENTICATION_FAILED'): self.gateway.admit(env)
    def test_rotation_fence(self):
        with self.assertRaises(RuntimeError): self.manager.rotate('trainos',b'e'*32,fault='prepared')
        with self.assertRaises(RecoveryRequired): self.gateway.admit(self.env())
    def test_audit_secret_mismatch(self):
        self.gateway.admit(self.env())
        other=MandatoryAdmissionGateway(self.manager,b'x'*32,clock=lambda:1000)
        with self.assertRaisesRegex(RecoveryRequired,'AUDIT_TAMPERED'): other.verify()
