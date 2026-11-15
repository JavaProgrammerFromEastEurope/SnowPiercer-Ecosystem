"""RAIL-TRUST-007: deterministic lock/fencing boundary tests."""
import multiprocessing as mp
import os
import signal
import socket
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from railsystem.anchored_admission import initialize, _locked, RecoveryRequired
from railsystem.recovery_boundary import ProductionBoundary, BoundaryError

class Provider:
    def read(self): return (0, '')
    def advance(self, old, new): return False

def hold_lock(path, ready):
    with _locked(Path(path)):
        ready.send('locked')
        time.sleep(20)

def start_worker(path, out):
    b = ProductionBoundary(Path(path), provider=Provider())
    try:
        b.start()
        out.send('started')
    except Exception as exc:
        out.send(type(exc).__name__)
    finally:
        b.close()

class AtomicStartupTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name) / 'state'; self.directory.mkdir(mode=0o700)
        initialize(self.directory)

    def test_preflight_inside_publication_lock(self):
        b = ProductionBoundary(self.directory, provider=Provider())
        def check(directory, provider):
            c = sqlite3.connect(self.directory / 'admission.sqlite3')
            try:
                c.execute("UPDATE state SET phase='PREPARED',pending_sequence=1,pending_nonce='x' WHERE id=1")
                c.commit()
            finally: c.close()
            raise RecoveryRequired('fence')
        with patch('railsystem.recovery_boundary._inspect_fence_locked', side_effect=check):
            with self.assertRaises(RecoveryRequired): b.start()
        self.assertFalse(b.socket_path.exists())

    def test_competing_starts_one_winner(self):
        a = ProductionBoundary(self.directory, provider=Provider())
        b = ProductionBoundary(self.directory, provider=Provider())
        a.start(); self.addCleanup(a.close)
        with self.assertRaises(BoundaryError): b.start()

    @unittest.skipUnless(hasattr(os, 'fork'), 'POSIX required')
    def test_sigkill_lock_holder_releases_fence(self):
        recv, send = mp.Pipe(duplex=False)
        proc = mp.Process(target=hold_lock, args=(str(self.directory), send))
        proc.start(); send.close()
        try:
            self.assertTrue(recv.poll(5))
            self.assertEqual(recv.recv(), 'locked')
            proc.kill(); proc.join(5)
            self.assertFalse(proc.is_alive())
            b = ProductionBoundary(self.directory, provider=Provider())
            b.start(); b.close()
        finally:
            if proc.is_alive(): proc.kill(); proc.join()
            recv.close()

    def test_prepared_fence_blocks_publication(self):
        c = sqlite3.connect(self.directory / 'admission.sqlite3')
        try:
            c.execute("UPDATE state SET phase='PREPARED',pending_sequence=1,pending_nonce='x' WHERE id=1")
            c.commit()
        finally:
            c.close()
        b = ProductionBoundary(self.directory, provider=Provider())
        with self.assertRaises(RecoveryRequired): b.start()
        self.assertFalse(b.socket_path.exists())

    def test_socket_symlink_refused(self):
        b = ProductionBoundary(self.directory, provider=Provider())
        b.socket_path.symlink_to(self.directory / 'anchor.json')
        with self.assertRaises(BoundaryError): b.start()
        self.assertTrue(b.socket_path.is_symlink())
