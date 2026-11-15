import copy
import unittest
from dataclasses import replace
from pathlib import Path
from lifesupport.core.registry import Registry
from lifesupport.core.lifecycle import Lifecycle, State, TransitionError, TRANSITIONS

ROOT = Path(__file__).resolve().parents[1]
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.r = Registry.load(ROOT/'data/registry.json')
        self.l = Lifecycle(self.r)
        self.id = 'LIFE-CORE-001'
        self.n = 0
    def move(self, cid, target):
        self.n += 1
        return self.l.transition(cid,target,event_id=f'e{self.n}',reason='test',actor='simulator',timestamp_utc=f'2026-11-14T01:{self.n//60:02d}:{self.n%60:02d}Z')
    def test_initial_state_all(self):
        self.assertEqual(len(self.l.snapshot()),20)
        self.assertTrue(all(s=='REGISTERED' for s in self.l.snapshot().values()))
    def test_valid_path(self):
        for state in [State.INITIALIZING,State.STANDBY,State.ACTIVE,State.DEGRADED,State.FAULT,State.ISOLATED,State.MAINTENANCE,State.INITIALIZING]: self.move(self.id,state)
        self.assertTrue(self.l.verify_audit())
        self.assertEqual(len(self.l.events),8)
    def test_no_jump(self):
        with self.assertRaises(TransitionError): self.move(self.id,State.ACTIVE)
    def test_same_state(self):
        with self.assertRaises(TransitionError): self.move(self.id,State.REGISTERED)
    def test_unknown_component(self):
        with self.assertRaises(TransitionError): self.move('UNKNOWN',State.INITIALIZING)
    def test_unknown_target(self):
        with self.assertRaises(TransitionError): self.move(self.id,'RUNNING')
    def test_duplicate_event_rejected(self):
        self.move(self.id,State.INITIALIZING)
        with self.assertRaises(TransitionError): self.l.transition(self.id,State.STANDBY,event_id='e1',reason='x',actor='x')
    def test_invalid_metadata_atomic(self):
        with self.assertRaises(TransitionError): self.l.transition(self.id,State.INITIALIZING,event_id=' ',reason='x',actor='x')
        self.assertEqual(len(self.l.events),0)
    def test_utc_required(self):
        with self.assertRaises(TransitionError): self.l.transition(self.id,State.INITIALIZING,event_id='x',reason='x',actor='x',timestamp_utc='2026-11-14T01:00:00+03:00')
    def test_monotonic_time(self):
        self.move(self.id,State.INITIALIZING)
        with self.assertRaises(TransitionError): self.l.transition(self.id,State.STANDBY,event_id='new',reason='x',actor='x',timestamp_utc='2026-11-13T00:00:00Z')
    def test_dependency_guard(self):
        dependent=next(cid for cid,c in self.r.components.items() if c['depends_on'])
        self.move(dependent,State.INITIALIZING);self.move(dependent,State.STANDBY)
        with self.assertRaises(TransitionError): self.move(dependent,State.ACTIVE)
    def test_reverse_dependency_guard(self):
        dependent=next(cid for cid,c in self.r.components.items() if c['depends_on']==[self.id])
        for cid in (self.id,dependent):
            for state in (State.INITIALIZING,State.STANDBY,State.ACTIVE): self.move(cid,state)
        with self.assertRaises(TransitionError): self.move(self.id,State.STANDBY)
        self.move(dependent,State.STANDBY)
        self.move(self.id,State.STANDBY)
    def test_snapshot_copy(self):
        s=self.l.snapshot();s[self.id]='ACTIVE';self.assertEqual(self.l.state(self.id),State.REGISTERED)
    def test_events_immutable(self):
        event=self.move(self.id,State.INITIALIZING)
        with self.assertRaises(Exception): event.actor='modified'
    def test_tamper_detected(self):
        self.move(self.id,State.INITIALIZING)
        self.l._events[0]=replace(self.l.events[0],reason='tampered')
        self.assertFalse(self.l.verify_audit())
    def test_hash_chain(self):
        a=self.move(self.id,State.INITIALIZING);b=self.move(self.id,State.STANDBY)
        self.assertEqual(b.previous_hash,a.event_hash)
        self.assertTrue(self.l.verify_audit())
    def test_transition_table_complete(self):
        self.assertEqual(set(TRANSITIONS),set(State))
        self.assertTrue(all(targets <= set(State) for targets in TRANSITIONS.values()))
    def test_no_actuation_interface(self):
        self.assertFalse(hasattr(self.l,'actuate'))
        self.assertFalse(hasattr(self.l,'send_command'))
    def test_failed_transition_no_event(self):
        with self.assertRaises(TransitionError): self.move(self.id,State.MAINTENANCE)
        self.assertEqual(self.l.events,())
        self.assertTrue(self.l.verify_audit())
