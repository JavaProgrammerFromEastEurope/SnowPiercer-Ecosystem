import contextlib
import multiprocessing
import os
import signal
import time
import sqlite3
import tempfile
import unittest
from pathlib import Path
from ai_cognition import (ReplayStore, IndependentAnchor, HardenedRotationManager,
    AnchoredAdmissionGateway, AuditCheckpoint, RecoveryRequired, signed_envelope)
K=b'a'*32; ROOT=b'b'*32; AUTH=b'c'*32; AUDIT=b'd'*32; CHECK=b'e'*32
OBS={'event_id':'event001','source':'trainos','severity':'warning','description':'ok'}

def external_insert(path,queue):
    try:
        with contextlib.closing(sqlite3.connect(path,timeout=2)) as db:
            db.execute('INSERT INTO seen VALUES (?,?,?,?)',('trainos','z'*16,'event001',1000))
        queue.put('bypass')
    except sqlite3.DatabaseError: queue.put('blocked')

def uncommitted_child(path,ready):
    with contextlib.closing(sqlite3.connect(path,timeout=5,isolation_level=None)) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS crash_probe (id INTEGER)")
        db.execute("INSERT INTO crash_probe VALUES (1)")
        ready.set()
        time.sleep(30)

def kill_process():
    os.kill(os.getpid(),signal.SIGKILL)

class AnchoredTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root=Path(tmp.name); self.db=str(root/'db'); self.root=root
        self.store=ReplayStore(self.db); self.addCleanup(self.store.close)
        self.manager=HardenedRotationManager(self.store,str(root/'legacy'),{'trainos':K},independent_anchor=IndependentAnchor(root/'independent',ROOT),recovery_secret=AUTH,bootstrap=True)
        self.manager.provision('trainos')
        self.checkpoint=AuditCheckpoint(root/'checkpoint',CHECK)
        self.gateway=AnchoredAdmissionGateway(self.manager,AUDIT,checkpoint=self.checkpoint,clock=lambda:1000,bootstrap=True)
    def env(self,nonce='a'*16): return signed_envelope(dict(OBS,event_id='event001' if nonce=='a'*16 else 'event002'),1000,nonce,K)
    def test_admit(self):
        self.gateway.admit(self.env()); self.assertEqual(self.gateway.verify()[0],1)
    def test_truncated_tail(self):
        self.gateway.admit(self.env())
        self.store._db.execute('DROP TRIGGER gateway_audit_delete')
        self.store._db.execute('DELETE FROM gateway_audit')
        with self.assertRaises(RecoveryRequired): self.gateway.verify()
    def test_checkpoint_tamper(self):
        self.checkpoint.path.write_text('corrupt')
        with self.assertRaises(RecoveryRequired): self.gateway.admit(self.env())
    def test_postcommit_fence_and_reconcile(self):
        with self.assertRaises(RuntimeError): self.gateway.admit(self.env(),fault='after_commit')
        with self.assertRaisesRegex(RecoveryRequired,'AUDIT_CHECKPOINT_MISMATCH'): self.gateway.admit(self.env('b'*16))
        with self.assertRaises(RecoveryRequired): self.gateway.reconcile()
        self.assertEqual(self.gateway.reconcile(authorized=True)[0],1)
        self.gateway.admit(self.env('b'*16))
    def test_reconcile_rejects_multiple_unanchored(self):
        with self.assertRaises(RuntimeError): self.gateway.admit(self.env(),fault='after_commit')
        self.store._db.execute('DROP TRIGGER gateway_audit_insert')
        self.store._db.execute('DROP TRIGGER gateway_seen_insert')
        # No authorization for multiple outstanding events, even if chain is valid.
        self.store._db.execute('INSERT INTO gateway_audit VALUES (?,?,?,?,?,?,?)',(2,'BAD','trainos','b'*16,0,'0'*64,'0'*64))
        with self.assertRaises(RecoveryRequired): self.gateway.reconcile(authorized=True)
    def test_consistent_database_rollback_detected(self):
        self.gateway.admit(self.env())
        # A privileged attacker can roll back the DB, but not independently held checkpoint.
        self.store._db.execute('DROP TRIGGER gateway_audit_delete')
        self.store._db.execute('DROP TRIGGER gateway_seen_delete')
        self.store._db.execute('DELETE FROM gateway_audit'); self.store._db.execute('DELETE FROM seen')
        with self.assertRaises(RecoveryRequired): self.gateway.verify()
    def test_external_process_direct_insert_fenced(self):
        ctx=multiprocessing.get_context('spawn'); q=ctx.Queue()
        p=ctx.Process(target=external_insert,args=(self.db,q)); p.start(); p.join(10)
        self.assertEqual(p.exitcode,0); self.assertEqual(q.get(timeout=3),'blocked'); q.close(); q.join_thread()
    @unittest.skipUnless(hasattr(signal,'SIGKILL'),'POSIX SIGKILL required')
    def test_real_sigkill_child(self):
        ctx=multiprocessing.get_context('spawn'); p=ctx.Process(target=kill_process)
        p.start(); p.join(10)
        self.assertEqual(p.exitcode,-signal.SIGKILL)
        self.assertEqual(self.gateway.verify()[0],0)
    @unittest.skipUnless(hasattr(signal,"SIGKILL"),"POSIX SIGKILL required")
    def test_sigkill_rolls_back_uncommitted_sqlite_transaction(self):
        ctx=multiprocessing.get_context("spawn"); ready=ctx.Event()
        p=ctx.Process(target=uncommitted_child,args=(self.db,ready)); p.start()
        try:
            self.assertTrue(ready.wait(10))
            os.kill(p.pid,signal.SIGKILL); p.join(10)
            self.assertEqual(p.exitcode,-signal.SIGKILL)
            self.assertEqual(self.gateway.verify()[0],0)
            with contextlib.closing(sqlite3.connect(self.db)) as db:
                self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='crash_probe'").fetchone())
        finally:
            if p.is_alive(): p.kill(); p.join()
    def test_schema_tamper_detected(self):
        self.store._db.execute('DROP TRIGGER gateway_seen_insert')
        with self.assertRaises(RecoveryRequired): self.gateway.verify()
    def test_checkpoint_missing(self):
        self.checkpoint.path.unlink()
        with self.assertRaises(RecoveryRequired): self.gateway.verify()
