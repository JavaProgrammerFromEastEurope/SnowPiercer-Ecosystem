import json, sqlite3, tempfile, unittest
from pathlib import Path
from lifesupport.core.registry import Registry
from lifesupport.core.admission import AdmittedLifecycle, AdmissionError
from lifesupport.core.hardening import HardenedLifecycle, guard_digest
ROOT=Path(__file__).resolve().parents[1]
class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db.sqlite'
        self.registry=Registry.from_dict(json.loads((ROOT/'data/registry.json').read_text()))
        self.cid=next(iter(self.registry.components))
    def open(self,cls=HardenedLifecycle):
        x=cls(self.registry,self.path,clock_ns=lambda:1000);self.addCleanup(x.close);return x
    def prepared(self):
        x=self.open();t=x.acquire('owner',ttl_ns=100);x.protect(t);x.harden(t);return x,t
    def test_unprotected_compatible(self):
        self.assertFalse(self.open().verify_integrity()['protected'])
    def test_migrate_v1(self):
        x=self.open();t=x.acquire('owner',ttl_ns=100);x.protect(t)
        self.assertEqual(x.verify_integrity()['version'],1);x.harden(t)
        self.assertEqual(x.verify_integrity()['version'],2)
    def test_harden_idempotent(self):
        x,t=self.prepared();x.harden(t);self.assertEqual(x.verify_integrity()['version'],2)
    def test_harden_requires_fence(self):
        x=self.open();t=x.acquire('owner',ttl_ns=100);x.protect(t)
        with self.assertRaises(Exception):x.harden(None)
    def test_harden_requires_protection(self):
        x=self.open();t=x.acquire('owner',ttl_ns=100)
        with self.assertRaises(AdmissionError):x.harden(t)
    def test_insert_guard_removed(self):
        x,t=self.prepared();x.db.execute('DROP TRIGGER ls_guard_insert')
        with self.assertRaises(AdmissionError):x.transition(self.cid,'INITIALIZING',event_id='x',reason='r',actor='a',token=t)
    def test_update_guard_changed(self):
        x,t=self.prepared();x.db.execute('DROP TRIGGER ls_guard_update');x.db.execute('CREATE TRIGGER ls_guard_update BEFORE UPDATE ON events BEGIN SELECT 1; END')
        with self.assertRaises(AdmissionError):x.verify_integrity()
    def test_delete_guard_removed(self):
        x,t=self.prepared();x.db.execute('DROP TRIGGER ls_guard_delete')
        with self.assertRaises(AdmissionError):x.recover(token=t)
    def test_seal_changed(self):
        x,t=self.prepared();x.db.execute("UPDATE life_guard_seal SET digest='bad'")
        with self.assertRaises(AdmissionError):x.verify_integrity()
    def test_seal_missing(self):
        x,t=self.prepared();x.db.execute('DROP TABLE life_guard_seal')
        with self.assertRaises(AdmissionError):x.verify_integrity()
    def test_open_detects_tamper(self):
        x,t=self.prepared();x.db.execute('DROP TRIGGER ls_guard_insert')
        with self.assertRaises(AdmissionError):self.open()
    def test_valid_write(self):
        x,t=self.prepared();x.transition(self.cid,'INITIALIZING',event_id='e1',reason='ok',actor='owner',token=t)
        self.assertEqual(len(x.recover(token=t).events),1)
    def test_legacy_rejected(self):
        x,t=self.prepared();old=self.open(AdmittedLifecycle)
        with self.assertRaises(Exception):old.transition(self.cid,'INITIALIZING',event_id='legacy',reason='r',actor='a',token=None)
    def test_rollback_bad_migration(self):
        x=self.open();t=x.acquire('owner',ttl_ns=100);x.protect(t);x.db.execute('DROP TRIGGER ls_guard_insert')
        with self.assertRaises(AdmissionError):x.harden(t)
        self.assertEqual(x.db.execute('SELECT version FROM life_admission').fetchone()[0],1)
    def test_digest_stable(self):
        self.assertEqual(len(guard_digest()),64)
    def test_reopen_clean(self):
        x,t=self.prepared();x.release(t);x.close();y=self.open();self.assertEqual(y.verify_integrity()['version'],2)
