import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import unittest
from lifesupport.core.registry import Registry
from lifesupport.core.hardening import HardenedLifecycle
from lifesupport.core.request_ledger import RequestLedgerAnchor, LedgerIntegrityError
from lifesupport.core.mandatory_ledger import MandatoryLedger
ROOT=pathlib.Path(__file__).resolve().parents[1]

class MandatoryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=pathlib.Path(self.tmp.name)/'db.sqlite'
        self.registry=Registry.load(ROOT/'data/registry.json')
        self.life=HardenedLifecycle(self.registry,self.path);self.addCleanup(self.life.close)
        token=self.life.acquire('setup',ttl_ns=10_000_000_000)
        self.life.protect(token);self.life.harden(token);self.life.release(token)
        self.anchor=RequestLedgerAnchor(pathlib.Path(self.tmp.name)/'anchor',b'k'*32)
        self.anchor.initialize(self.life.db)
        self.gate=MandatoryLedger(self.life,self.anchor)
        self.cid=next(iter(self.registry.components))
    def req(self,rid='r1',eid='e1'):
        return dict(op='transition',request_id=rid,component_id=self.cid,next_state='INITIALIZING',event_id=eid,reason='test')
    def test_clean(self):self.assertEqual(self.gate.recover()['count'],0)
    def test_write(self):
        self.assertFalse(self.gate.apply(self.req(),42)['replayed'])
        self.assertTrue(self.gate.apply(self.req(),42)['replayed'])
        self.assertEqual(self.gate.recover()['count'],1)
    def test_crash_after_intent(self):
        def fault(phase):
            if phase=='after_intent':raise RuntimeError('crash')
        with self.assertRaises(RuntimeError):self.gate.apply(self.req(),42,fault=fault)
        self.assertEqual(self.gate.recover()['count'],0)
        self.assertFalse(self.gate.intent.exists())
    def test_crash_after_commit(self):
        def fault(phase):
            if phase=='after_commit':raise RuntimeError('crash')
        with self.assertRaises(RuntimeError):self.gate.apply(self.req(),42,fault=fault)
        self.assertEqual(self.gate.recover()['count'],1)
        self.assertTrue(self.gate.apply(self.req(),42)['replayed'])
    def test_crash_before_anchor(self):
        def fault(phase):
            if phase=='before_anchor':raise RuntimeError('crash')
        with self.assertRaises(RuntimeError):self.gate.apply(self.req(),42,fault=fault)
        self.assertEqual(self.gate.recover()['count'],1)
    def test_anchor_tamper(self):
        self.gate.apply(self.req(),42)
        self.anchor.path.write_text('{}')
        with self.assertRaises(LedgerIntegrityError):self.gate.recover()
    def test_receipt_tamper(self):
        self.gate.apply(self.req(),42)
        self.life.db.execute('DELETE FROM life_request_receipts')
        with self.assertRaises(LedgerIntegrityError):self.gate.recover()
    def test_pending_tamper(self):
        def fault(phase):
            if phase=='after_intent':raise RuntimeError()
        with self.assertRaises(RuntimeError):self.gate.apply(self.req(),42,fault=fault)
        self.gate.intent.write_text('{}')
        with self.assertRaises(LedgerIntegrityError):self.gate.recover()
    def test_wrong_key(self):
        with self.assertRaises(LedgerIntegrityError):MandatoryLedger(self.life,RequestLedgerAnchor(self.anchor.path,b'x'*32)).recover()
    def test_conflict(self):
        self.gate.apply(self.req(),42)
        with self.assertRaises(Exception):self.gate.apply(self.req(eid='different'),42)
    def test_reopen(self):
        self.gate.apply(self.req(),42)
        self.life.close();self.life=HardenedLifecycle(self.registry,self.path)
        self.gate=MandatoryLedger(self.life,self.anchor)
        self.assertEqual(self.gate.recover()['count'],1)
    def test_sigkill_after_commit(self):
        code='''import os,signal,sys,json
from lifesupport.core.registry import Registry
from lifesupport.core.hardening import HardenedLifecycle
from lifesupport.core.request_ledger import RequestLedgerAnchor
from lifesupport.core.mandatory_ledger import MandatoryLedger
l=HardenedLifecycle(Registry.load(sys.argv[1]),sys.argv[2]);g=MandatoryLedger(l,RequestLedgerAnchor(sys.argv[3],b'k'*32))
def fault(p):
 if p=='after_commit':os.kill(os.getpid(),signal.SIGKILL)
g.apply(json.loads(sys.argv[4]),42,fault=fault)
'''
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        p=subprocess.run([sys.executable,'-c',code,str(ROOT/'data/registry.json'),str(self.path),str(self.anchor.path),json.dumps(self.req())],env=env,capture_output=True,timeout=15)
        self.assertEqual(p.returncode,-signal.SIGKILL)
        self.assertEqual(self.gate.recover()['count'],1)
    def test_sigkill_after_intent(self):
        code='''import os,signal,sys,json
from lifesupport.core.registry import Registry
from lifesupport.core.hardening import HardenedLifecycle
from lifesupport.core.request_ledger import RequestLedgerAnchor
from lifesupport.core.mandatory_ledger import MandatoryLedger
l=HardenedLifecycle(Registry.load(sys.argv[1]),sys.argv[2]);g=MandatoryLedger(l,RequestLedgerAnchor(sys.argv[3],b'k'*32))
def fault(p):
 if p=='after_intent':os.kill(os.getpid(),signal.SIGKILL)
g.apply(json.loads(sys.argv[4]),42,fault=fault)
'''
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        p=subprocess.run([sys.executable,'-c',code,str(ROOT/'data/registry.json'),str(self.path),str(self.anchor.path),json.dumps(self.req())],env=env,capture_output=True,timeout=15)
        self.assertEqual(p.returncode,-signal.SIGKILL)
        self.assertEqual(self.gate.recover()['count'],0)

class ServiceIntegrationContractTests(unittest.TestCase):
    def test_supervisor_arguments(self):
        from lifesupport.core.mandatory_ledger import MandatoryLedgerSupervisor
        s=MandatoryLedgerSupervisor('/tmp/r','/tmp/db','/tmp/socket',allowed_uids={42},anchor_path='/tmp/anchor',key_file='/tmp/key')
        self.assertEqual(s.cli_module,'lifesupport.mandatory_ledger_cli')
        self.assertEqual(s.extra_args,('--anchor','/tmp/anchor','--key-file','/tmp/key'))
    def test_startup_preflight_requires_anchor(self):
        from lifesupport.core.mandatory_ledger import MandatoryLedgerService
        from lifesupport.core.registry import Registry
        from lifesupport.core.hardening import HardenedLifecycle
        from lifesupport.core.request_ledger import LedgerIntegrityError
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            registry=Registry.load(ROOT/'data/registry.json')
            life=HardenedLifecycle(registry,root/'db')
            try:
                token=life.acquire('setup',ttl_ns=10_000_000_000)
                life.protect(token);life.harden(token);life.release(token)
                svc=MandatoryLedgerService(ROOT/'data/registry.json',root/'db',root/'sock',allowed_uids={42},anchor_path=root/'missing',key=b'k'*32)
                with self.assertRaises(LedgerIntegrityError):svc.preflight(life)
            finally:life.close()
