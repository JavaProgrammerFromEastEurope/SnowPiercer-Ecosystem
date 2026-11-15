"""RAIL-TRUST-008: IPC lifecycle regression; no hardware safety certification."""
import os
import socket
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from railsystem.anchored_admission import initialize
from railsystem.recovery_boundary import ProductionBoundary, BoundaryError

class Provider:
    def read(self): return (0, '')
    def advance(self, old, new): return False

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.directory = Path(t.name) / 'state'; self.directory.mkdir(mode=0o700)
        initialize(self.directory)

    def test_recovery_after_start_blocks_request(self):
        if not hasattr(socket, 'SO_PEERCRED'): self.skipTest('Linux only')
        b = ProductionBoundary(self.directory, provider=Provider()); b.start(); self.addCleanup(b.close)
        c = sqlite3.connect(self.directory / 'admission.sqlite3')
        try:
            c.execute("UPDATE state SET phase='PREPARED',pending_sequence=1,pending_nonce='x' WHERE id=1")
            c.commit()
        finally: c.close()
        result = []
        thread = threading.Thread(target=lambda: result.append(b.handle_one(root=self.directory, baseline={}, attestation={}, trust={})))
        thread.start()
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(3); client.connect(str(b.socket_path)); client.sendall(b'ADMIT\n')
            self.assertIn(b'BLOCKED', client.recv(1024))
        thread.join(3)
        self.assertFalse(thread.is_alive()); self.assertEqual(result, ['BLOCKED'])

    def test_replaced_socket_not_served(self):
        b = ProductionBoundary(self.directory, provider=Provider()); b.start()
        b.socket_path.unlink(); b.socket_path.symlink_to(self.directory / 'anchor.json')
        with self.assertRaises(BoundaryError): b.handle_one(root=self.directory, baseline={}, attestation={}, trust={})
        b.close(); self.assertTrue(b.socket_path.is_symlink())

    def test_legacy_request_rejected(self):
        if not hasattr(socket, 'SO_PEERCRED'): self.skipTest('Linux only')
        b = ProductionBoundary(self.directory, provider=Provider()); b.start(); self.addCleanup(b.close)
        outcome = []
        t = threading.Thread(target=lambda: outcome.append(b.handle_one(root=self.directory, baseline={}, attestation={}, trust={})))
        t.start()
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(3); client.connect(str(b.socket_path)); client.sendall(b'RELEASE\n')
            self.assertIn(b'BLOCKED', client.recv(1024))
        t.join(3); self.assertEqual(outcome, ['BLOCKED'])
