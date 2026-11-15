import multiprocessing as mp
import os
import signal
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from railsystem.anchored_admission import initialize, _locked
from railsystem.recovery_boundary import ProductionBoundary
from railsystem.unified_admission import admit
from railsystem.production_fencing import IndependentAnchorUnavailable

class Provider:
    def read(self): return (0, '')
    def advance(self, old, new): return False

def hold_lock(path, ready):
    with _locked(path):
        ready.set()
        time.sleep(20)

class Lifecycle009(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.directory=Path(tmp.name)/'state'; self.directory.mkdir(mode=0o700)
        initialize(self.directory)

    def test_sigkill_releases_lifecycle_lock(self):
        ready=mp.Event()
        process=mp.Process(target=hold_lock,args=(self.directory,ready)); process.start()
        try:
            self.assertTrue(ready.wait(4))
            os.kill(process.pid,signal.SIGKILL)
            process.join(4)
            self.assertEqual(process.exitcode,-signal.SIGKILL)
            with _locked(self.directory): pass
        finally:
            if process.is_alive(): process.kill(); process.join()

    def test_no_nested_flock_on_admit(self):
        boundary=ProductionBoundary(self.directory,provider=Provider()); boundary.start()
        self.addCleanup(boundary.close)
        statuses=[]
        thread=threading.Thread(target=lambda: statuses.append(boundary.handle_one(root=self.directory,baseline={},attestation={},trust={})))
        thread.start()
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(3); client.connect(str(boundary.socket_path)); client.sendall(b'ADMIT\n')
            self.assertIn(b'BLOCKED',client.recv(1024))
        thread.join(4)
        self.assertFalse(thread.is_alive()); self.assertEqual(statuses,['BLOCKED'])

    def test_peer_uid_mismatch_fails_closed(self):
        boundary=ProductionBoundary(self.directory,provider=Provider()); boundary.start(); self.addCleanup(boundary.close)
        statuses=[]
        with patch('railsystem.recovery_boundary._peer_uid',return_value=os.geteuid()+1):
            thread=threading.Thread(target=lambda: statuses.append(boundary.handle_one(root=self.directory,baseline={},attestation={},trust={})))
            thread.start()
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(3); client.connect(str(boundary.socket_path)); client.sendall(b'ADMIT\n')
                self.assertIn(b'BLOCKED',client.recv(1024))
            thread.join(4)
        self.assertEqual(statuses,['BLOCKED'])

    def test_prepared_fences_admission(self):
        conn=sqlite3.connect(self.directory/'admission.sqlite3')
        conn.execute("UPDATE state SET phase='PREPARED',pending_sequence=1,pending_nonce='n' WHERE id=1")
        conn.commit(); conn.close()
        with self.assertRaises(Exception):
            admit(self.directory,baseline={},attestation={},trust={},state_dir=self.directory,provider=Provider())

    def test_missing_independent_provider_fails_closed(self):
        with self.assertRaises(IndependentAnchorUnavailable):
            ProductionBoundary(self.directory).start()
