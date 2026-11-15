import multiprocessing as mp
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from snowpiercer_logistics import *

ADMIN = Principal('admin-1','admin')
OP = Principal('operator-1','operator')
AUD = Principal('auditor-1','auditor')

def crash_worker(path, mode):
    with LogisticsLedger(path) as db:
        db.transition_cargo(OP, 'crash-command', 'c', CargoState.IN_TRANSIT)
    os._exit(137)

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name)/'ledger.sqlite')
        self.db = LogisticsLedger(self.path)
        self.db.add_container(ADMIN,'setup-container',Container('box',100))
        self.db.add_location(ADMIN,'setup-a',Location('a','warehouse'))
        self.db.add_location(ADMIN,'setup-b',Location('b','warehouse'))
        self.db.register_cargo(OP,'register',Cargo('c','box','a'))
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def test_transfer_and_idempotency(self):
        self.db.transition_cargo(OP,'store','c',CargoState.STORED)
        self.db.transition_cargo(OP,'transit','c',CargoState.IN_TRANSIT)
        t=Transfer('t','c','a','b')
        first=self.db.record_transfer(OP,'move',t)
        self.assertEqual(first,self.db.record_transfer(OP,'move',t))
        self.assertEqual(self.db.get_cargo(AUD,'c').location_id,'b')
        self.assertEqual(self.db.verify(AUD)['events'],7)
        with self.assertRaises(ConflictError): self.db.record_transfer(OP,'move',Transfer('other','c','a','b'))
    def test_authorization(self):
        with self.assertRaises(AuthorizationError): self.db.transition_cargo(AUD,'x','c',CargoState.STORED)
        with self.assertRaises(AuthorizationError): self.db.add_location(OP,'x',Location('x','warehouse'))
        with self.assertRaises(AuthorizationError): self.db.get_cargo(Principal('x','unknown'),'c')
    def test_invalid_transitions_rollback(self):
        before=self.db.verify(AUD)['events']
        with self.assertRaises(ConflictError): self.db.transition_cargo(OP,'bad','c',CargoState.DELIVERED)
        self.assertEqual(self.db.verify(AUD)['events'],before)
        self.assertEqual(self.db.get_cargo(AUD,'c').state,CargoState.REGISTERED)
    def test_mission_fsm(self):
        self.db.create_mission(OP,'mission',Mission('m','c'))
        self.db.transition_mission(OP,'active','m',MissionState.ACTIVE)
        self.db.transition_mission(OP,'complete','m',MissionState.COMPLETED)
        with self.assertRaises(ConflictError): self.db.transition_mission(OP,'bad-m','m',MissionState.ACTIVE)
        self.db.verify(AUD)
    def test_reopen_replay(self):
        self.db.transition_cargo(OP,'store','c',CargoState.STORED)
        self.db.close()
        self.db=LogisticsLedger(self.path)
        self.assertEqual(self.db.transition_cargo(OP,'store','c',CargoState.STORED)['state'],'STORED')
        self.assertEqual(self.db.verify(AUD)['events'],5)
    def test_detect_hash_corruption(self):
        self.db._db.execute("UPDATE events SET event_hash='bad' WHERE seq=1")
        with self.assertRaises(InvariantError): self.db.verify(AUD)
    def test_crash_after_commit_replay(self):
        self.db.transition_cargo(OP,'store','c',CargoState.STORED)
        self.db.close()
        p=mp.Process(target=crash_worker,args=(self.path,'after'))
        p.start(); p.join(10)
        self.assertEqual(p.exitcode,137)
        self.db=LogisticsLedger(self.path)
        self.assertEqual(self.db.get_cargo(AUD,'c').state,CargoState.IN_TRANSIT)
        self.db.transition_cargo(OP,'crash-command','c',CargoState.IN_TRANSIT)
        self.assertEqual(self.db.verify(AUD)['events'],6)
    def test_concurrent_duplicate(self):
        self.db.transition_cargo(OP,'store','c',CargoState.STORED)
        self.db.close()
        def worker(path):
            with LogisticsLedger(path) as db:
                db.transition_cargo(OP,'same','c',CargoState.IN_TRANSIT)
        # separate processes via fork where available; threads otherwise tested via same db
        import threading
        self.db=LogisticsLedger(self.path)
        errors=[]
        def task():
            try: self.db.transition_cargo(OP,'same','c',CargoState.IN_TRANSIT)
            except Exception as exc: errors.append(exc)
        threads=[threading.Thread(target=task) for _ in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors,[])
        self.assertEqual(self.db.verify(AUD)['events'],6)
    def test_invalid_references(self):
        with self.assertRaises(sqlite3.IntegrityError): self.db.create_mission(OP,'unknown',Mission('m','missing'))
        self.assertEqual(self.db.verify(AUD)['events'],4)

if __name__ == '__main__': unittest.main()
