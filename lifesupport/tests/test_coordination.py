from contextlib import contextmanager
@contextmanager
def managed_connect(*args, **kwargs):
    import sqlite3
    db=sqlite3.connect(*args, **kwargs)
    try:
        with db:
            yield db
    finally:
        db.close()

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from lifesupport.core.registry import Registry
from lifesupport.core.coordination import FencedLifecycle, FencingError, FenceToken
from lifesupport.core.persistence import PersistentLifecycle

ROOT=Path(__file__).resolve().parents[1]

class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'events.sqlite'
        self.registry=Registry.from_dict(json.loads((ROOT/'data/registry.json').read_text()))
        self.cid=next(iter(self.registry.components))
        self.now=1000
        self.clock=lambda:self.now
    def open(self):
        p=FencedLifecycle(self.registry,self.path,clock_ns=self.clock)
        self.addCleanup(p.close)
        return p
    def step(self,p,tok,eid,state='INITIALIZING'):
        return p.transition(self.cid,state,event_id=eid,reason='test',actor='tester',token=tok)
    def test_initial_acquire(self):
        a=self.open(); t=a.acquire('a',ttl_ns=100)
        self.assertEqual(t.epoch,1)
    def test_exclusive_owner(self):
        a=self.open();b=self.open();a.acquire('a',ttl_ns=100)
        with self.assertRaises(FencingError): b.acquire('b',ttl_ns=100)
    def test_transition_with_fence(self):
        a=self.open();t=a.acquire('a',ttl_ns=100);self.step(a,t,'e1')
        self.assertEqual(len(a.lifecycle.events),1)
    def test_no_token_rejected(self):
        a=self.open();a.acquire('a',ttl_ns=100)
        with self.assertRaises(FencingError): self.step(a,None,'e1')
    def test_expiry_rejects(self):
        a=self.open();t=a.acquire('a',ttl_ns=100);self.now=1100
        with self.assertRaises(FencingError): self.step(a,t,'e1')
    def test_takeover_increments_epoch(self):
        a=self.open();b=self.open();t=a.acquire('a',ttl_ns=100);self.now=1100
        t2=b.acquire('b',ttl_ns=100);self.assertEqual(t2.epoch,2)
        with self.assertRaises(FencingError): self.step(a,t,'e1')
    def test_stale_same_owner(self):
        a=self.open();t=a.acquire('a',ttl_ns=100);self.now=1100
        t2=a.acquire('a',ttl_ns=100)
        with self.assertRaises(FencingError): self.step(a,t,'e1')
        self.step(a,t2,'e2')
    def test_release_allows_takeover(self):
        a=self.open();b=self.open();t=a.acquire('a',ttl_ns=100);a.release(t)
        self.assertEqual(b.acquire('b',ttl_ns=100).epoch,2)
    def test_double_release_rejected(self):
        a=self.open();t=a.acquire('a',ttl_ns=100);a.release(t)
        with self.assertRaises(FencingError): a.release(t)
    def test_renew_updates_token(self):
        a=self.open();t=a.acquire('a',ttl_ns=100);t2=a.renew(t,ttl_ns=200)
        with self.assertRaises(FencingError):self.step(a,t,'e1')
        self.step(a,t2,'e2')
    def test_renew_expired_rejected(self):
        a=self.open();t=a.acquire('a',ttl_ns=100);self.now=1100
        with self.assertRaises(FencingError):a.renew(t,ttl_ns=100)
    def test_negative_ttl_rejected(self):
        a=self.open()
        with self.assertRaises(FencingError):a.acquire('a',ttl_ns=-1)
    def test_empty_owner_rejected(self):
        a=self.open()
        with self.assertRaises(FencingError):a.acquire('',ttl_ns=100)
    def test_recover_requires_fence(self):
        a=self.open();t=a.acquire('a',ttl_ns=100)
        with self.assertRaises(FencingError):a.recover()
        self.assertEqual(len(a.recover(token=t).events),0)
    def test_invalid_transition_rollback(self):
        a=self.open();t=a.acquire('a',ttl_ns=100)
        with self.assertRaises(Exception):self.step(a,t,'bad','ACTIVE')
        self.step(a,t,'good');self.assertEqual(len(a.lifecycle.events),1)
    def test_corrupt_journal_blocks_acquire(self):
        a=self.open();t=a.acquire('a',ttl_ns=100);self.step(a,t,'e1');a.release(t)
        with managed_connect(self.path) as db:db.execute("UPDATE events SET payload='{' WHERE sequence=1")
        with self.assertRaises(Exception):self.open()
    def test_persists_epoch_across_restart(self):
        a=self.open();t=a.acquire('a',ttl_ns=100);a.release(t);a.close()
        b=self.open();self.assertEqual(b.acquire('b',ttl_ns=100).epoch,2)
    def test_no_partial_commit_after_expiry(self):
        a=self.open();t=a.acquire('a',ttl_ns=100)
        self.now=1100
        with self.assertRaises(FencingError):self.step(a,t,'e1')
        self.assertEqual(a.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
    def test_registry_fingerprint_fenced(self):
        a=self.open();t=a.acquire('a',ttl_ns=100);a.release(t)
        with managed_connect(self.path) as db:db.execute("UPDATE coordination SET registry_fingerprint='wrong'")
        with self.assertRaises(FencingError):a.acquire('b',ttl_ns=100)
    def test_two_writers_sequential(self):
        a=self.open();b=self.open();t=a.acquire('a',ttl_ns=100);self.step(a,t,'e1');a.release(t)
        u=b.acquire('b',ttl_ns=100);self.step(b,u,'e2','STANDBY')
        self.assertEqual(len(b.lifecycle.events),2)
    def test_legacy_is_not_fenced(self):
        a=self.open();t=a.acquire('a',ttl_ns=100)
        with PersistentLifecycle(self.registry,self.path) as old:
            old.transition(self.cid,'INITIALIZING',event_id='legacy',reason='test',actor='old')
        self.assertEqual(len(a.recover(token=t).events),1)
    def test_invalid_token_type(self):
        a=self.open();a.acquire('a',ttl_ns=100)
        with self.assertRaises(FencingError):self.step(a,{'owner':'a'},'e1')
    def test_expiry_during_operation_rolls_back(self):
        a=self.open();t=a.acquire('a',ttl_ns=100)
        calls=iter([1000,1100]);a._clock=lambda:next(calls)
        with self.assertRaises(FencingError):self.step(a,t,'e1')
        self.assertEqual(a.db.execute('SELECT count(*) FROM events').fetchone()[0],0)

if __name__=='__main__':unittest.main()
