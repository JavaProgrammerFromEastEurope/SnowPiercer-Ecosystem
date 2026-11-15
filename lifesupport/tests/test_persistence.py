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
from lifesupport.core.lifecycle import State, TransitionError
from lifesupport.core.persistence import PersistentLifecycle, RecoveryError

ROOT = Path(__file__).resolve().parents[1]

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'journal.db'
        self.registry = Registry.from_dict(json.loads((ROOT/'data/registry.json').read_text()))
        self.cid = next(iter(self.registry.components))

    def open(self):
        return PersistentLifecycle(self.registry, self.path)

    def step(self, store, state, event_id):
        return store.transition(self.cid, state, event_id=event_id, actor='tester', reason='test')

    def test_initial_empty(self):
        with self.open() as p:
            self.assertEqual(p.lifecycle.state(self.cid), State.REGISTERED)

    def test_restart_replay(self):
        with self.open() as p:
            self.step(p, 'INITIALIZING', 'e1')
        with self.open() as p:
            self.assertEqual(p.lifecycle.state(self.cid), State.INITIALIZING)
            self.assertTrue(p.lifecycle.verify_audit())

    def test_duplicate_after_restart(self):
        with self.open() as p:
            self.step(p, 'INITIALIZING', 'e1')
        with self.open() as p:
            with self.assertRaises(TransitionError):
                self.step(p, 'STANDBY', 'e1')
            self.assertEqual(len(p.lifecycle.events), 1)

    def test_invalid_transition_atomic(self):
        with self.open() as p:
            with self.assertRaises(TransitionError):
                self.step(p, 'ACTIVE', 'e1')
            self.assertEqual(len(p.lifecycle.events), 0)
        with self.open() as p:
            self.assertEqual(len(p.lifecycle.events), 0)

    def test_tamper_payload_detected(self):
        with self.open() as p:
            self.step(p, 'INITIALIZING', 'e1')
        with managed_connect(self.path) as db:
            db.execute("UPDATE events SET payload=replace(payload,'tester','attacker')")
        with self.assertRaises(RecoveryError):
            self.open()

    def test_missing_middle_detected(self):
        with self.open() as p:
            self.step(p, 'INITIALIZING', 'e1')
            self.step(p, 'STANDBY', 'e2')
        with managed_connect(self.path) as db:
            db.execute('DELETE FROM events WHERE sequence=1')
        with self.assertRaises(RecoveryError):
            self.open()

    def test_fingerprint_mismatch(self):
        with self.open():
            pass
        with managed_connect(self.path) as db:
            db.execute("UPDATE metadata SET value='different'")
        with self.assertRaises(RecoveryError):
            self.open()

    def test_stale_writer_replays(self):
        with self.open() as first, self.open() as second:
            self.step(first, 'INITIALIZING', 'e1')
            self.step(second, 'STANDBY', 'e2')
            self.assertEqual(second.lifecycle.state(self.cid), State.STANDBY)
            first.recover()
            self.assertEqual(first.lifecycle.state(self.cid), State.STANDBY)

    def test_stale_duplicate_rejected(self):
        with self.open() as first, self.open() as second:
            self.step(first, 'INITIALIZING', 'e1')
            with self.assertRaises(TransitionError):
                self.step(second, 'STANDBY', 'e1')

    def test_failed_insert_rollback(self):
        with self.open() as p:
            self.step(p, 'INITIALIZING', 'e1')
            with self.assertRaises(TransitionError):
                self.step(p, 'ACTIVE', 'e2')
            self.step(p, 'STANDBY', 'e3')
            self.assertEqual(len(p.lifecycle.events), 2)

    def test_recover_after_external_event(self):
        with self.open() as a, self.open() as b:
            self.step(a, 'INITIALIZING', 'e1')
            self.assertEqual(b.recover().state(self.cid), State.INITIALIZING)

    def test_truncated_json_detected(self):
        with self.open() as p:
            self.step(p, 'INITIALIZING', 'e1')
        with managed_connect(self.path) as db:
            db.execute("UPDATE events SET payload='{' WHERE sequence=1")
        with self.assertRaises(RecoveryError):
            self.open()

    def test_event_sequence_persisted(self):
        with self.open() as p:
            self.assertEqual(self.step(p, 'INITIALIZING', 'e1').sequence, 1)
            self.assertEqual(self.step(p, 'STANDBY', 'e2').sequence, 2)
        with self.open() as p:
            self.assertEqual([e.sequence for e in p.lifecycle.events], [1, 2])

    def test_event_index_tamper_detected(self):
        with self.open() as p:
            self.step(p, 'INITIALIZING', 'e1')
        with managed_connect(self.path) as db:
            db.execute("UPDATE events SET event_id='other' WHERE sequence=1")
        with self.assertRaises(RecoveryError):
            self.open()

    def test_no_hardware_interface(self):
        with self.open() as p:
            self.assertFalse(hasattr(p, 'send_hardware_command'))

if __name__ == '__main__':
    unittest.main()
