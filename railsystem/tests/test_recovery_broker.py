import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from railsystem.anchored_admission import initialize
from railsystem.recovery_broker import RecoveryBroker, BrokerDenied, authorize_peer
from railsystem.production_fencing import IndependentAnchorUnavailable

class Provider:
    def read(self): return (0, '')

class RecoveryBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'private'
        self.path.mkdir(mode=0o700)
        initialize(self.path)

    def test_no_identity_fails_closed(self):
        with self.assertRaises(BrokerDenied):
            RecoveryBroker(self.path, provider=Provider()).start()

    def test_no_external_provider_fails_closed(self):
        with self.assertRaises(IndependentAnchorUnavailable):
            RecoveryBroker(self.path, allowed_uids=frozenset({os.geteuid()})).start()

    @unittest.skipUnless(hasattr(socket, 'SO_PEERCRED'), 'Linux peer credentials required')
    def test_actual_peer_identity(self):
        a, b = socket.socketpair()
        try:
            self.assertEqual(authorize_peer(a, frozenset({os.geteuid()})), os.geteuid())
            with self.assertRaises(BrokerDenied):
                authorize_peer(a, frozenset({os.geteuid() + 100000}))
        finally:
            a.close(); b.close()

    def test_bad_allowlist(self):
        a, b = socket.socketpair()
        try:
            for value in (set(), frozenset(), frozenset({'0'})):
                with self.subTest(value=value), self.assertRaises(BrokerDenied):
                    authorize_peer(a, value)
        finally:
            a.close(); b.close()

    def test_socket_substitution_is_detected(self):
        broker = RecoveryBroker(self.path, provider=Provider(), allowed_uids=frozenset({os.geteuid()}))
        broker.start()
        try:
            broker._verify_path()
            broker.path.unlink()
            broker.path.symlink_to(self.path / 'anchor.json')
            with self.assertRaises(BrokerDenied): broker._verify_path()
        finally:
            broker.close()

    def test_recovery_not_triggered_by_unsupported_command(self):
        broker = RecoveryBroker(self.path, provider=Provider(), allowed_uids=frozenset({os.geteuid()}))
        broker.start()
        try:
            import threading
            result = []
            t = threading.Thread(target=lambda: result.append(broker.handle_one(permit={}, recovery_public_key='')))
            t.start()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(broker.path))
                client.sendall(b'LEGACY\n')
                self.assertIn(b'BLOCKED', client.recv(512))
            t.join(timeout=3)
            self.assertFalse(t.is_alive())
            self.assertEqual(result, ['BLOCKED'])
        finally:
            broker.close()
