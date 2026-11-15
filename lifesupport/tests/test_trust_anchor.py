import json, tempfile, unittest, sqlite3
from pathlib import Path
from lifesupport.core.registry import Registry
from lifesupport.core.trust_anchor import TrustedLifecycle, AnchorError
from lifesupport.core.hardening import HardenedLifecycle
ROOT=Path(__file__).resolve().parents[1]
class TrustAnchorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'store.db';self.anchor=Path(self.tmp.name)/'trust'/'anchor.json'
        self.registry=Registry.from_dict(json.loads((ROOT/'data/registry.json').read_text()))
        self.cid=next(iter(self.registry.components))
        self.secret=b's'*32
    def open(self,cls=TrustedLifecycle,secret=None):
        if cls is TrustedLifecycle:
            obj=cls(self.registry,self.db,anchor_path=self.anchor,secret=secret or self.secret,clock_ns=lambda:1000)
        else:obj=cls(self.registry,self.db,clock_ns=lambda:1000)
        self.addCleanup(obj.close);return obj
    def prepared(self):
        x=self.open();t=x.acquire('owner',ttl_ns=100);x.protect(t);x.harden(t);x.establish_anchor(t);return x,t
    def test_enrollment(self):
        x,t=self.prepared();self.assertEqual(x.verify_anchor()['admission_version'],2)
    def test_missing_anchor(self):
        x,t=self.prepared();self.anchor.unlink()
        with self.assertRaises(AnchorError):x.recover(token=t)
    def test_wrong_key(self):
        x,t=self.prepared()
        with self.assertRaises(AnchorError):self.open(secret=b'z'*32)
    def test_modified_mac(self):
        x,t=self.prepared();d=json.loads(self.anchor.read_text());d['mac']='0'*64;self.anchor.write_text(json.dumps(d))
        with self.assertRaises(AnchorError):x.verify_anchor()
    def test_modified_payload(self):
        x,t=self.prepared();d=json.loads(self.anchor.read_text());d['payload']['guard_digest']='a'*64;self.anchor.write_text(json.dumps(d))
        with self.assertRaises(AnchorError):x.verify_anchor()
    def test_truncated_file(self):
        x,t=self.prepared();self.anchor.write_text('{')
        with self.assertRaises(AnchorError):x.verify_anchor()
    def test_rollback_epoch(self):
        x,t=self.prepared();x.release(t);t2=x.acquire('other',ttl_ns=100);x.advance_anchor(t2)
        x.db.execute('UPDATE coordination SET epoch=1 WHERE singleton=1')
        with self.assertRaises(AnchorError):x.verify_anchor()
    def test_valid_write(self):
        x,t=self.prepared();x.transition(self.cid,'INITIALIZING',event_id='event',reason='test',actor='operator',token=t)
        self.assertEqual(len(x.recover(token=t).events),1)
    def test_tamper_guard(self):
        x,t=self.prepared();x.db.execute('DROP TRIGGER ls_guard_insert')
        with self.assertRaises(Exception):x.verify_anchor()
    def test_double_enrollment(self):
        x,t=self.prepared()
        with self.assertRaises(AnchorError):x.establish_anchor(t)
    def test_short_secret(self):
        with self.assertRaises(AnchorError):self.open(secret=b'x')
    def test_enroll_requires_v2(self):
        x=self.open();t=x.acquire('owner',ttl_ns=100)
        with self.assertRaises(AnchorError):x.establish_anchor(t)
    def test_enroll_requires_fence(self):
        x=self.open();t=x.acquire('owner',ttl_ns=100);x.protect(t);x.harden(t)
        with self.assertRaises(Exception):x.establish_anchor(None)
    def test_reopen(self):
        x,t=self.prepared();x.release(t);x.close();y=self.open();self.assertEqual(y.verify_anchor()['version'],1)
    def test_advance_anchor(self):
        x,t=self.prepared();x.release(t);t2=x.acquire('next',ttl_ns=100)
        self.assertEqual(x.advance_anchor(t2)['epoch_floor'],2)
    def test_advance_requires_fence(self):
        x,t=self.prepared()
        with self.assertRaises(Exception):x.advance_anchor(None)
    def test_no_anchor_blocks_acquire(self):
        x,t=self.prepared();x.release(t);self.anchor.unlink()
        with self.assertRaises(AnchorError):x.acquire('next',ttl_ns=100)
    def test_legacy_unprotected(self):
        x=self.open(HardenedLifecycle);self.assertFalse(x.verify_integrity()['protected'])
