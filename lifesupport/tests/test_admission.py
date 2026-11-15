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
from lifesupport.core.persistence import PersistentLifecycle
from lifesupport.core.coordination import FencedLifecycle
from lifesupport.core.admission import AdmittedLifecycle, AdmissionError

ROOT=Path(__file__).resolve().parents[1]
class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'life.db'
        self.registry=Registry.from_dict(json.loads((ROOT/'data/registry.json').read_text()))
        self.cid=next(iter(self.registry.components))
        self.clock=lambda:1000
    def open(self,cls=AdmittedLifecycle):
        p=cls(self.registry,self.path,clock_ns=self.clock) if cls is not PersistentLifecycle else cls(self.registry,self.path)
        self.addCleanup(p.close)
        return p
    def test_protection_blocks_legacy(self):
        p=self.open();t=p.acquire('a',ttl_ns=100);p.protect(t)
        legacy=self.open(PersistentLifecycle)
        with self.assertRaises(sqlite3.OperationalError):
            legacy.transition(self.cid,'INITIALIZING',event_id='bad',reason='x',actor='legacy')
        self.assertEqual(p.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
    def test_admitted_append(self):
        p=self.open();t=p.acquire('a',ttl_ns=100);p.protect(t)
        p.transition(self.cid,'INITIALIZING',event_id='ok',reason='x',actor='a',token=t)
        self.assertEqual(len(p.recover(token=t).events),1)
    def test_stale_token_rejected(self):
        p=self.open();t=p.acquire('a',ttl_ns=100);p.protect(t);p.release(t)
        with self.assertRaises(Exception):p.transition(self.cid,'INITIALIZING',event_id='bad',reason='x',actor='a',token=t)
    def test_protect_requires_token(self):
        p=self.open();p.acquire('a',ttl_ns=100)
        with self.assertRaises(Exception):p.protect(None)
    def test_migration_idempotent(self):
        p=self.open();t=p.acquire('a',ttl_ns=100);p.protect(t);p.protect(t)
        self.assertEqual(p.db.execute('SELECT version FROM life_admission').fetchone()[0],1)
    def test_migration_legacy_events(self):
        old=self.open(PersistentLifecycle)
        old.transition(self.cid,'INITIALIZING',event_id='pre',reason='x',actor='old')
        p=self.open();t=p.acquire('a',ttl_ns=100);p.protect(t)
        p.transition(self.cid,'STANDBY',event_id='post',reason='x',actor='a',token=t)
        self.assertEqual(len(p.recover(token=t).events),2)
    def test_raw_sql_rejected(self):
        p=self.open();t=p.acquire('a',ttl_ns=100);p.protect(t)
        with managed_connect(self.path) as db:
            with self.assertRaises(sqlite3.OperationalError):db.execute("INSERT INTO events VALUES (1,'raw','{}')")
    def test_delete_and_update_rejected(self):
        p=self.open();t=p.acquire('a',ttl_ns=100);p.protect(t)
        p.transition(self.cid,'INITIALIZING',event_id='ok',reason='x',actor='a',token=t)
        with self.assertRaises(sqlite3.IntegrityError):p.db.execute('DELETE FROM events')
        with self.assertRaises(sqlite3.IntegrityError):p.db.execute("UPDATE events SET payload='{}'")
    def test_restart_protection_persists(self):
        p=self.open();t=p.acquire('a',ttl_ns=100);p.protect(t);p.release(t);p.close()
        old=self.open(PersistentLifecycle)
        with self.assertRaises(sqlite3.OperationalError):old.transition(self.cid,'INITIALIZING',event_id='bad',reason='x',actor='legacy')
        q=self.open();u=q.acquire('b',ttl_ns=100);q.transition(self.cid,'INITIALIZING',event_id='ok',reason='x',actor='b',token=u)
    def test_unprotected_legacy_unchanged(self):
        p=self.open(PersistentLifecycle)
        p.transition(self.cid,'INITIALIZING',event_id='ok',reason='x',actor='legacy')
        self.assertEqual(len(p.recover().events),1)
    def test_failed_transition_flag_reset(self):
        p=self.open();t=p.acquire('a',ttl_ns=100);p.protect(t)
        with self.assertRaises(Exception):p.transition(self.cid,'ACTIVE',event_id='bad',reason='x',actor='a',token=t)
        self.assertFalse(p._admitted)
    def test_failed_protect_rolls_back(self):
        p=self.open();p.acquire('a',ttl_ns=100)
        with self.assertRaises(Exception):p.protect(None)
        self.assertFalse(bool(p.db.execute("SELECT name FROM sqlite_master WHERE name='life_admission'").fetchone()))
