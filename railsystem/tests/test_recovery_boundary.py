import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from railsystem.anchored_admission import initialize, RecoveryRequired
from railsystem.recovery_boundary import ProductionBoundary, BoundaryError, preflight, _verify_socket
from railsystem.production_fencing import IndependentAnchorUnavailable

class Provider:
    def read(self): return (0, '')
    def advance(self, old, new): return False

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.directory = Path(t.name) / 'state'; self.directory.mkdir(mode=0o700)
        initialize(self.directory)
    def test_missing_provider_fail_closed(self):
        with self.assertRaises(IndependentAnchorUnavailable): ProductionBoundary(self.directory).start()
    def test_start_and_close(self):
        b = ProductionBoundary(self.directory, provider=Provider()); b.start()
        self.assertTrue(b.socket_path.exists()); b.close()
        self.assertFalse(b.socket_path.exists())
    def test_double_start_refused(self):
        b = ProductionBoundary(self.directory, provider=Provider()); b.start(); self.addCleanup(b.close)
        with self.assertRaises(BoundaryError): b.start()
    def test_existing_socket_refused(self):
        p = self.directory / 'release.sock'; p.symlink_to(self.directory / 'anchor.json')
        with self.assertRaises(BoundaryError): ProductionBoundary(self.directory, provider=Provider()).start()
        self.assertTrue(p.is_symlink())
    def test_socket_replacement_detected_and_not_deleted(self):
        b = ProductionBoundary(self.directory, provider=Provider()); b.start()
        b.socket_path.unlink(); b.socket_path.symlink_to(self.directory / 'anchor.json')
        with self.assertRaises(BoundaryError): b.handle_one(root=self.directory,baseline={},attestation={},trust={})
        b.close(); self.assertTrue(b.socket_path.is_symlink())
    def test_preflight_not_admission(self):
        self.assertEqual(preflight(self.directory, provider=Provider())['status'], 'CONSISTENT')
    def test_recovery_fence_blocks_start(self):
        import sqlite3
        c = sqlite3.connect(self.directory / 'admission.sqlite3')
        c.execute("UPDATE state SET phase='PREPARED',pending_sequence=1,pending_nonce='abc' WHERE id=1"); c.commit(); c.close()
        with self.assertRaises(RecoveryRequired): ProductionBoundary(self.directory, provider=Provider()).start()
    @unittest.skipUnless(hasattr(socket,'SO_PEERCRED'), 'Linux SO_PEERCRED required')
    def test_unsupported_request_blocked(self):
        b = ProductionBoundary(self.directory, provider=Provider()); b.start(); self.addCleanup(b.close)
        outcome = []
        def worker(): outcome.append(b.handle_one(root=self.directory,baseline={},attestation={},trust={}))
        t = threading.Thread(target=worker); t.start()
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(b.socket_path)); client.sendall(b'LEGACY\n')
            self.assertIn(b'BLOCKED', client.recv(1024))
        t.join(5); self.assertFalse(t.is_alive()); self.assertEqual(outcome, ['BLOCKED'])
    @unittest.skipUnless(hasattr(socket,'SO_PEERCRED'), 'Linux SO_PEERCRED required')
    def test_invalid_attestation_blocked(self):
        b = ProductionBoundary(self.directory, provider=Provider()); b.start(); self.addCleanup(b.close)
        outcome=[]
        t=threading.Thread(target=lambda: outcome.append(b.handle_one(root=self.directory,baseline={},attestation={},trust={})))
        t.start()
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(b.socket_path)); client.sendall(b'ADMIT\n')
            self.assertIn(b'BLOCKED', client.recv(1024))
        t.join(5); self.assertFalse(t.is_alive()); self.assertEqual(outcome,['BLOCKED'])
    def test_unsafe_directory(self):
        os.chmod(self.directory, 0o755)
        with self.assertRaises(ValueError): ProductionBoundary(self.directory, provider=Provider())
