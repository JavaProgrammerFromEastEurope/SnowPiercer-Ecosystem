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
from lifesupport.core.checkpoints import (CheckpointError, create_checkpoint, verify_checkpoint,
    create_backup, verify_backup, restore_backup)
ROOT = Path(__file__).resolve().parents[1]
KEY = b'K' * 32

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.dir = Path(t.name)
        self.registry = Registry.from_dict(json.loads((ROOT/'data/registry.json').read_text()))
        self.cid = next(iter(self.registry.components))
        self.db = self.dir/'journal.db'; self.anchor = self.dir/'anchor.json'
        self.backup = self.dir/'backup.db'; self.manifest = self.dir/'backup.json'
    def open(self): return PersistentLifecycle(self.registry, self.db)
    def step(self, s, state, eid):
        s.transition(self.cid, state, event_id=eid, reason='test', actor='test')
    def test_empty_anchor(self):
        with self.open() as s:
            self.assertEqual(create_checkpoint(s,self.anchor,KEY)['sequence'],0)
            verify_checkpoint(s,self.anchor,KEY)
    def test_anchor_roundtrip(self):
        with self.open() as s:
            self.step(s,'INITIALIZING','a'); create_checkpoint(s,self.anchor,KEY)
        with self.open() as s: verify_checkpoint(s,self.anchor,KEY)
    def test_anchor_allows_new_events(self):
        with self.open() as s:
            self.step(s,'INITIALIZING','a'); create_checkpoint(s,self.anchor,KEY)
            self.step(s,'STANDBY','b'); verify_checkpoint(s,self.anchor,KEY)
            with self.assertRaises(CheckpointError): verify_checkpoint(s,self.anchor,KEY,allow_newer_journal=False)
    def test_detect_truncated_tail(self):
        with self.open() as s:
            self.step(s,'INITIALIZING','a'); self.step(s,'STANDBY','b'); create_checkpoint(s,self.anchor,KEY)
        with managed_connect(self.db) as db: db.execute('DELETE FROM events WHERE sequence=2')
        with self.open() as s:
            with self.assertRaises(CheckpointError): verify_checkpoint(s,self.anchor,KEY)
    def test_detect_rewritten_history(self):
        with self.open() as s:
            self.step(s,'INITIALIZING','a'); create_checkpoint(s,self.anchor,KEY)
        with managed_connect(self.db) as db: db.execute('DELETE FROM events')
        with self.open() as s:
            self.step(s,'INITIALIZING','b')
            with self.assertRaises(CheckpointError): verify_checkpoint(s,self.anchor,KEY)
    def test_bad_key(self):
        with self.open() as s:
            create_checkpoint(s,self.anchor,KEY)
            with self.assertRaises(CheckpointError): verify_checkpoint(s,self.anchor,b'X'*32)
    def test_short_key(self):
        with self.open() as s:
            with self.assertRaises(CheckpointError): create_checkpoint(s,self.anchor,b'abc')
    def test_tampered_anchor(self):
        with self.open() as s:
            create_checkpoint(s,self.anchor,KEY)
            doc=json.loads(self.anchor.read_text()); doc['payload']['sequence']=12
            self.anchor.write_text(json.dumps(doc))
            with self.assertRaises(CheckpointError): verify_checkpoint(s,self.anchor,KEY)
    def test_anchor_no_rollback(self):
        with self.open() as s:
            self.step(s,'INITIALIZING','a'); create_checkpoint(s,self.anchor,KEY)
        with managed_connect(self.db) as db: db.execute('DELETE FROM events')
        with self.open() as s:
            with self.assertRaises(CheckpointError): create_checkpoint(s,self.anchor,KEY)
    def test_backup_roundtrip(self):
        with self.open() as s:
            self.step(s,'INITIALIZING','a'); create_checkpoint(s,self.anchor,KEY)
            create_backup(s,self.backup,self.manifest,KEY,self.anchor)
        self.assertEqual(verify_backup(self.registry,self.backup,self.manifest,KEY,self.anchor)['sequence'],1)
        restored=restore_backup(self.registry,self.backup,self.manifest,self.dir/'restored.db',KEY,self.anchor)
        with PersistentLifecycle(self.registry,restored) as s: self.assertEqual(len(s.lifecycle.events),1)
    def test_backup_tamper(self):
        with self.open() as s: create_backup(s,self.backup,self.manifest,KEY)
        with self.backup.open('ab') as f: f.write(b'garbage')
        with self.assertRaises(CheckpointError): verify_backup(self.registry,self.backup,self.manifest,KEY)
    def test_manifest_tamper(self):
        with self.open() as s: create_backup(s,self.backup,self.manifest,KEY)
        doc=json.loads(self.manifest.read_text()); doc['payload']['sequence']=99
        self.manifest.write_text(json.dumps(doc))
        with self.assertRaises(CheckpointError): verify_backup(self.registry,self.backup,self.manifest,KEY)
    def test_wrong_backup_key(self):
        with self.open() as s: create_backup(s,self.backup,self.manifest,KEY)
        with self.assertRaises(CheckpointError): verify_backup(self.registry,self.backup,self.manifest,b'Z'*32)
    def test_no_overwrite_restore(self):
        with self.open() as s: create_backup(s,self.backup,self.manifest,KEY)
        destination=self.dir/'existing.db'; destination.write_bytes(b'KEEP')
        with self.assertRaises(FileExistsError): restore_backup(self.registry,self.backup,self.manifest,destination,KEY)
        self.assertEqual(destination.read_bytes(),b'KEEP')
    def test_backup_rejects_old_anchor(self):
        with self.open() as s:
            self.step(s,'INITIALIZING','a'); create_checkpoint(s,self.anchor,KEY)
            create_backup(s,self.backup,self.manifest,KEY,self.anchor)
        with managed_connect(self.backup) as db: db.execute('DELETE FROM events')
        with self.assertRaises(CheckpointError): verify_backup(self.registry,self.backup,self.manifest,KEY,self.anchor)
    def test_distinct_paths(self):
        with self.open() as s:
            with self.assertRaises(CheckpointError): create_backup(s,self.db,self.manifest,KEY)
