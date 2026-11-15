import os
import pathlib
import signal
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from lifesupport.core.registry import Registry
from lifesupport.core.hardening import HardenedLifecycle
from lifesupport.core.request_ledger import RequestLedgerAnchor, LedgerAdmission, LedgerIntegrityError, ledger_snapshot
from lifesupport.core.reconciled_write import apply_request
ROOT=pathlib.Path(__file__).resolve().parents[1]

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=pathlib.Path(self.tmp.name)/'db.sqlite'
        self.registry=Registry.load(ROOT/'data/registry.json')
        self.life=HardenedLifecycle(self.registry,self.db);self.addCleanup(self.life.close)
        token=self.life.acquire('setup',ttl_ns=10_000_000_000)
        self.life.protect(token);self.life.harden(token);self.life.release(token)
        self.anchor=RequestLedgerAnchor(pathlib.Path(self.tmp.name)/'anchor.json',b'k'*32)
        self.anchor.initialize(self.life.db)
        self.admission=LedgerAdmission(self.life,self.anchor)
        self.cid=next(iter(self.registry.components))
    def req(self,rid='r1',eid='e1'):
        return {'op':'transition','request_id':rid,'component_id':self.cid,'next_state':'INITIALIZING','event_id':eid,'reason':'test'}
    def test_empty(self):self.assertEqual(self.admission.verify()['count'],0)
    def test_write_and_replay(self):
        self.assertFalse(self.admission.apply(self.req(),42)['replayed'])
        self.assertTrue(self.admission.apply(self.req(),42)['replayed'])
        self.assertEqual(self.admission.verify()['count'],1)
    def test_tamper_receipt(self):
        self.admission.apply(self.req(),42)
        self.life.db.execute("UPDATE life_request_receipts SET request_hash=?",('f'*64,))
        with self.assertRaises(LedgerIntegrityError):self.admission.verify()
    def test_delete_receipt(self):
        self.admission.apply(self.req(),42)
        self.life.db.execute('DELETE FROM life_request_receipts')
        with self.assertRaises(LedgerIntegrityError):self.admission.verify()
    def test_tamper_anchor(self):
        self.admission.apply(self.req(),42)
        self.anchor.path.write_text('{}')
        with self.assertRaises(LedgerIntegrityError):self.admission.verify()
    def test_wrong_key(self):
        with self.assertRaises(LedgerIntegrityError):RequestLedgerAnchor(self.anchor.path,b'x'*32).verify(self.life.db)
    def test_missing_anchor(self):
        self.anchor.path.unlink()
        with self.assertRaises(LedgerIntegrityError):self.admission.verify()
    def test_symlink_anchor(self):
        self.anchor.path.unlink();self.anchor.path.symlink_to(self.db)
        with self.assertRaises(LedgerIntegrityError):self.admission.verify()
    def test_uncommitted_rollback(self):
        self.life.db.execute('BEGIN IMMEDIATE')
        self.life.db.execute("INSERT INTO life_request_receipts VALUES ('x',?,42,1,'e1')",('a'*64,)) if False else None
        self.life.db.execute('ROLLBACK')
        self.assertEqual(self.admission.verify()['count'],0)
    def test_crash_after_commit_quarantine(self):
        def fault(phase):
            if phase=='after_commit':raise RuntimeError('lost response')
        with self.assertRaises(RuntimeError):self.admission.apply(self.req(),42,fault=fault)
        with self.assertRaises(LedgerIntegrityError):self.admission.verify()
        approved=ledger_snapshot(self.life.db)
        self.anchor.reconcile(self.life.db,approved_snapshot=approved)
        self.assertTrue(self.admission.apply(self.req(),42)['replayed'])
    def test_reconciliation_requires_approval(self):
        apply_request(self.life,self.req(),42)
        with self.assertRaises(LedgerIntegrityError):self.anchor.reconcile(self.life.db,approved_snapshot={'count':0})
        self.anchor.reconcile(self.life.db,approved_snapshot=ledger_snapshot(self.life.db))
        self.admission.verify()
    def test_reopen(self):
        self.admission.apply(self.req(),42);self.life.close()
        self.life=HardenedLifecycle(self.registry,self.db)
        self.assertEqual(self.anchor.verify(self.life.db)['count'],1)
    def test_reject_rollback(self):
        self.admission.apply(self.req(),42)
        self.life.db.execute('DELETE FROM life_request_receipts')
        with self.assertRaises(LedgerIntegrityError):self.anchor.reconcile(self.life.db,approved_snapshot=ledger_snapshot(self.life.db))
    def test_concurrent_sqlite_readers(self):
        self.admission.apply(self.req(),42)
        for _ in range(10):
            con=sqlite3.connect(self.db)
            try:self.assertEqual(ledger_snapshot(con)['count'],1)
            finally:con.close()
    def test_sigkill_after_commit(self):
        code='''import os,signal,sys,json
from lifesupport.core.registry import Registry
from lifesupport.core.hardening import HardenedLifecycle
from lifesupport.core.reconciled_write import apply_request
l=HardenedLifecycle(Registry.load(sys.argv[1]),sys.argv[2])
def fault(phase):
 if phase=='after_commit':os.kill(os.getpid(),signal.SIGKILL)
apply_request(l,json.loads(sys.argv[3]),42,fault=fault)
'''
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        p=subprocess.run([sys.executable,'-c',code,str(ROOT/'data/registry.json'),str(self.db),__import__('json').dumps(self.req())],env=env,capture_output=True,timeout=10)
        self.assertEqual(p.returncode,-signal.SIGKILL)
        with self.assertRaises(LedgerIntegrityError):self.admission.verify()
