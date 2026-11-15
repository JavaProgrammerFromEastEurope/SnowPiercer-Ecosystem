"""RAIL-TRUST-011: local fault injection, NOT an independent assurance suite.

File-backed test doubles deliberately DO NOT meet production rollback guarantees.
"""
import base64
import fcntl
import json
import os
import signal
import socket
import sqlite3
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from railsystem.anchored_admission import initialize, _read_anchor, _state, _connect, RecoveryRequired
from railsystem.durable_permits import IndependentPermitLedger, PermitLedgerUnavailable
from railsystem.privileged_recovery import PrivilegedRecoveryBroker, PrivilegedBrokerDenied
from railsystem.production_fencing import IndependentAnchorUnavailable
from railsystem.unified_admission import recover, admit
from railsystem.provenance import candidate_baseline
from railsystem.trust import canonical

ROOT = Path(__file__).resolve().parents[1]
GID, CLIENT_A, CLIENT_B = 63080, 63081, 63082


def atomic_json(path, data):
    tmp = path.with_suffix('.new')
    with open(tmp, 'w') as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(data, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


class LocalFileAnchor:
    """Test-only same-host CAS; no protected anti-rollback property."""
    def __init__(self, root):
        self.path = root / 'mock_remote_anchor.json'
        self.lock = root / 'mock_remote_anchor.lock'
        if not self.path.exists(): atomic_json(self.path, [0, ''])

    def read(self):
        return tuple(json.loads(self.path.read_text()))

    def advance(self, old, new):
        with open(self.lock, 'a+b') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            if self.read() != tuple(old): return False
            atomic_json(self.path, list(new))
            return True


class LocalFileLedger:
    """Test-only separate file; atomic locally, not rollback-resistant."""
    def __init__(self, root):
        self.path = root / 'mock_remote_permits.json'
        self.lock = root / 'mock_remote_permits.lock'
        if not self.path.exists(): atomic_json(self.path, [])

    def check_ready(self):
        if not isinstance(json.loads(self.path.read_text()), list):
            raise PermitLedgerUnavailable('invalid mock ledger')
        return True

    def consume_once(self, digest, *, sequence, action):
        assert action == 'reconcile' and type(sequence) is int
        with open(self.lock, 'a+b') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            values = json.loads(self.path.read_text())
            if digest in values: return False
            values.append(digest)
            atomic_json(self.path, values)
            return True


class FalseLedger(LocalFileLedger):
    def consume_once(self, digest, *, sequence, action): return False


class RecoveryStage011(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o700)
        initialize(self.state)
        self.ipc = self.root / 'transport'
        self.ipc.mkdir(mode=0o750)
        if os.geteuid() == 0:
            os.chown(self.ipc, os.geteuid(), GID)
            self.root.chmod(0o755)
        self.gid = self.ipc.stat().st_gid
        self.provider = LocalFileAnchor(self.root)
        self.ledger = LocalFileLedger(self.root)
        self.key = Ed25519PrivateKey.generate()
        raw = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.public = base64.b64encode(raw).decode()

    def prepared(self, seq=1, nonce='nonce-new'):
        c = _connect(self.state)
        try:
            c.execute('BEGIN IMMEDIATE')
            c.execute("UPDATE state SET phase='PREPARED',pending_sequence=?,pending_nonce=? WHERE id=1", (seq, nonce))
            c.execute('COMMIT')
        finally: c.close()

    def permit(self, identifier='p'*25, seq=1):
        payload = {'domain':'snowpiercer.railsystem.recovery.v1', 'sequence':seq,
                   'action':'reconcile', 'permit_id':identifier}
        return {'payload': payload, 'signature': base64.b64encode(self.key.sign(canonical(payload))).decode()}

    def broker(self, allowed=None, provider=None, ledger=None):
        return PrivilegedRecoveryBroker(self.state, self.ipc, transport_gid=self.gid,
            allowed_uids=frozenset({CLIENT_A}) if allowed is None else allowed,
            provider=self.provider if provider is None else provider,
            permit_store=self.ledger if ledger is None else ledger)

    def test_missing_services_fail_closed(self):
        with self.assertRaises(IndependentAnchorUnavailable):
            self.broker(provider=__import__('railsystem.production_fencing', fromlist=['IndependentAnchor']).IndependentAnchor()).start()
        with self.assertRaises(PermitLedgerUnavailable):
            self.broker(ledger=IndependentPermitLedger()).start()
        self.assertFalse((self.ipc/'recovery-v011.sock').exists())

    def test_false_readiness_blocks_startup_and_recovery(self):
        class NotReady(LocalFileLedger):
            def check_ready(self): return False
        with self.assertRaises(PermitLedgerUnavailable):
            self.broker(ledger=NotReady(self.root)).start()
        self.prepared()
        with self.assertRaises(RecoveryRequired):
            recover(self.state, provider=self.provider, permit=self.permit(),
                    recovery_public_key=self.public, permit_store=NotReady(self.root))
        self.assertFalse((self.ipc/'recovery-v011.sock').exists())

    def test_invalid_anchor_contract_blocks_startup(self):
        class MalformedAnchor:
            def read(self): return ('not-a-sequence', '')
        with self.assertRaises(Exception):
            self.broker(provider=MalformedAnchor()).start()
        self.assertFalse((self.ipc/'recovery-v011.sock').exists())

    def test_invalid_uid_and_directory_permissions(self):
        with self.assertRaises(PrivilegedBrokerDenied): self.broker(allowed=frozenset()).start()
        with self.assertRaises(PrivilegedBrokerDenied): self.broker(allowed=frozenset({os.geteuid()})).start()
        self.ipc.chmod(0o777)
        with self.assertRaises(PrivilegedBrokerDenied): self.broker()

    def test_existing_path_and_socket_substitution(self):
        broker = self.broker(); broker.start()
        try:
            with self.assertRaises(PrivilegedBrokerDenied): self.broker().start()
            broker.path.unlink()
            broker.path.symlink_to(self.state/'anchor.json')
            with self.assertRaises(PrivilegedBrokerDenied): broker._verify_path()
        finally:
            broker.close()
        self.assertTrue(broker.path.is_symlink())  # never unlink unknown object

    def test_recovery_requires_external_one_use(self):
        self.prepared()
        with self.assertRaises(PermitLedgerUnavailable):
            recover(self.state, provider=self.provider, permit=self.permit(),
                    recovery_public_key=self.public, permit_store=IndependentPermitLedger())
        with self.assertRaises(RecoveryRequired):
            recover(self.state, provider=self.provider, permit=self.permit(),
                    recovery_public_key=self.public, permit_store=FalseLedger(self.root))
        c = _connect(self.state)
        try: self.assertEqual(_state(c)[2], 'PREPARED')
        finally: c.close()

    def test_external_consumption_blocks_local_rollback_replay(self):
        self.prepared()
        p = self.permit()
        result = recover(self.state, provider=self.provider, permit=p,
                         recovery_public_key=self.public, permit_store=self.ledger)
        self.assertEqual(result['status'], 'RECOVERED')
        self.prepared()
        with self.assertRaises(Exception):
            recover(self.state, provider=self.provider, permit=p,
                    recovery_public_key=self.public, permit_store=self.ledger)
        # Simulate rollback of the *local* permit table; the external test
        # ledger still refuses the same signed permit.
        c = _connect(self.state)
        try: c.execute('DELETE FROM unified_permits')
        finally: c.close()
        with self.assertRaises(RecoveryRequired):
            recover(self.state, provider=self.provider, permit=p,
                    recovery_public_key=self.public, permit_store=self.ledger)
        self.assertEqual(recover(self.state, provider=self.provider, permit=self.permit('q'*25),
            recovery_public_key=self.public, permit_store=self.ledger)['status'], 'RECOVERED')

    def test_tampered_or_wrong_scope_permit_does_not_consume(self):
        self.prepared()
        p = self.permit(); p['payload']['sequence'] = 2
        with self.assertRaises(Exception):
            recover(self.state, provider=self.provider, permit=p,
                    recovery_public_key=self.public, permit_store=self.ledger)
        self.assertEqual(json.loads(self.ledger.path.read_text()), [])

    @unittest.skipUnless(hasattr(os,'fork'), 'requires POSIX fork')
    def test_sigkill_recovery_matrix(self):
        points = ('before_permit_consume', 'after_permit_consume',
                  'after_recovery_anchor','before_recovery_commit', 'after_recovery_commit')
        for index, point in enumerate(points):
            with self.subTest(point=point):
                # Restore empty PREPARED/permit storage between each scenario.
                c = _connect(self.state)
                try:
                    c.execute("UPDATE state SET sequence=0,nonces='[]',phase='PREPARED',pending_sequence=1,pending_nonce='n' WHERE id=1")
                    c.execute('CREATE TABLE IF NOT EXISTS unified_permits (digest TEXT PRIMARY KEY)')
                    c.execute('DELETE FROM unified_permits')
                finally: c.close()
                from railsystem.anchored_admission import _atomic_anchor
                _atomic_anchor(self.state/'anchor.json', {'sequence':0, 'nonce':''})
                atomic_json(self.ledger.path, [])
                permit = self.permit(chr(97+index)*25)
                pid=os.fork()
                if pid == 0:
                    recover(self.state, provider=self.provider, permit=permit,
                            recovery_public_key=self.public, permit_store=self.ledger,
                            kill_at=point)
                    os._exit(91)
                _, status = os.waitpid(pid, 0)
                self.assertEqual(os.waitstatus_to_exitcode(status), -signal.SIGKILL)
                c = _connect(self.state)
                try: phase=_state(c)[2]
                finally: c.close()
                self.assertEqual(phase, 'IDLE' if point == 'after_recovery_commit' else 'PREPARED')
                if point != 'before_permit_consume' and point != 'after_recovery_commit':
                    with self.assertRaises(Exception):
                        recover(self.state, provider=self.provider, permit=permit,
                                recovery_public_key=self.public, permit_store=self.ledger)
                    self.assertEqual(recover(self.state, provider=self.provider,
                        permit=self.permit(chr(104+index)*25), recovery_public_key=self.public,
                        permit_store=self.ledger)['status'], 'RECOVERED')

    @unittest.skipUnless(os.geteuid() == 0 and hasattr(socket, 'SO_PEERCRED'),
                         'requires Linux root and SO_PEERCRED')
    def test_real_cross_uid_reconcile_and_unauthorized_peer(self):
        self.prepared()
        broker = self.broker()
        broker.start()
        try:
            for uid, expected in ((CLIENT_B, 'BLOCKED'), (CLIENT_A, 'RECOVERED')):
                # Fork before the server starts servicing, drop the real OS
                # credentials in the child. No monkeypatched peer identities.
                read_fd, write_fd = os.pipe()
                pid = os.fork()
                if pid == 0:
                    os.close(read_fd)
                    try:
                        os.setgroups([self.gid]); os.setgid(self.gid); os.setuid(uid)
                        private_denied = not os.access(self.state, os.R_OK | os.X_OK)
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                            sock.settimeout(3)
                            sock.connect(str(broker.path)); sock.sendall(b'RECONCILE\n')
                            answer = sock.recv(512).decode()
                        os.write(write_fd, json.dumps({'answer':json.loads(answer), 'private_denied':private_denied}).encode())
                    except BaseException as exc:
                        os.write(write_fd, json.dumps({'error':str(exc)}).encode())
                    os.close(write_fd); os._exit(0)
                os.close(write_fd)
                try:
                    result = broker.handle_one(permit=self.permit(), recovery_public_key=self.public)
                    self.assertEqual(result, expected)
                    payload = json.loads(os.read(read_fd, 4096))
                    self.assertNotIn('error', payload)
                    self.assertTrue(payload['private_denied'])
                    self.assertEqual(payload['answer']['status'], expected)
                finally:
                    os.close(read_fd)
                    _, status = os.waitpid(pid, 0)
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        finally:
            broker.close()

    @unittest.skipUnless(os.geteuid() == 0 and hasattr(socket, 'SO_PEERCRED'),
                         'requires Linux root and SO_PEERCRED')
    def test_cross_uid_invalid_command(self):
        broker = self.broker(); broker.start()
        try:
            pid = os.fork()
            if pid == 0:
                os.setgroups([self.gid]); os.setgid(self.gid); os.setuid(CLIENT_A)
                with socket.socket(socket.AF_UNIX) as s:
                    s.connect(str(broker.path)); s.sendall(b'LEGACY\n'); s.recv(512)
                os._exit(0)
            self.assertEqual(broker.handle_one(permit=self.permit(), recovery_public_key=self.public), 'BLOCKED')
            self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]), 0)
        finally: broker.close()

    @unittest.skipUnless(hasattr(os, 'fork'), 'requires POSIX fork')
    def test_sigkill_admission_sqlite_external_anchor_matrix(self):
        # Cryptographic attestation is real; the internal regression gate is
        # mocked only to keep crash-point injection deterministic and bounded.
        baseline = candidate_baseline(ROOT, 'r011-fault-matrix')
        pub = base64.b64encode(self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        trust = {'schema_version':1, 'keys':{'fault-signer':{'public_key':pub, 'revoked':False}}}
        payload = {'domain':'snowpiercer.railsystem.release.v1',
            'baseline_id':baseline['baseline_id'], 'manifest_digest':baseline['manifest_digest'],
            'key_id':'fault-signer', 'sequence':1, 'nonce':'nonce00112233445566'}
        attestation = {'schema_version':1, 'payload':payload,
                       'signature':base64.b64encode(self.key.sign(canonical(payload))).decode()}
        points = ('before_prepare', 'after_prepare', 'before_external',
                  'after_external', 'before_local', 'after_local',
                  'before_final_commit', 'after_final_commit')
        from railsystem.anchored_admission import _atomic_anchor
        for point in points:
            with self.subTest(point=point):
                c = _connect(self.state)
                try:
                    c.execute("UPDATE state SET sequence=0,nonces='[]',phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1")
                finally: c.close()
                _atomic_anchor(self.state/'anchor.json', {'sequence':0, 'nonce':''})
                atomic_json(self.provider.path, [0, ''])
                pid = os.fork()
                if pid == 0:
                    with patch('railsystem.unified_admission.evaluate', return_value={'status':'PASS'}):
                        admit(ROOT, baseline=baseline, attestation=attestation,
                              trust=trust, state_dir=self.state, provider=self.provider,
                              kill_at=point)
                    os._exit(97)
                _, status = os.waitpid(pid, 0)
                self.assertEqual(os.waitstatus_to_exitcode(status), -signal.SIGKILL)
                c = _connect(self.state)
                try: seq, raw, phase, pseq, nonce = _state(c)
                finally: c.close()
                self.assertEqual(phase, 'IDLE' if point in ('before_prepare','after_final_commit') else 'PREPARED')
                if phase == 'PREPARED':
                    with self.assertRaises(RecoveryRequired):
                        from railsystem.production_fencing import inspect_fence
                        inspect_fence(self.state, self.provider)
                if point in ('after_external','before_local','after_local','before_final_commit','after_final_commit'):
                    self.assertEqual(self.provider.read()[0], 1)
                else:
                    self.assertEqual(self.provider.read()[0], 0)

    @unittest.skipUnless(hasattr(os, 'fork'), 'requires POSIX fork')
    def test_sigkill_broker_leaves_stale_socket_fail_closed(self):
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            broker = self.broker()
            broker.start()
            os.write(w, b'READY')
            signal.pause()
            os._exit(0)
        os.close(w)
        try:
            self.assertEqual(os.read(r, 5), b'READY')
            os.kill(pid, signal.SIGKILL)
            self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]), -signal.SIGKILL)
            with self.assertRaises(PrivilegedBrokerDenied):
                self.broker().start()
            # Only a service manager with verified path identity may clean up
            # the orphaned socket. Here it is owned by this test.
            self.assertTrue(stat.S_ISSOCK((self.ipc/'recovery-v011.sock').lstat().st_mode))
            (self.ipc/'recovery-v011.sock').unlink()
        finally:
            os.close(r)
            try: os.waitpid(pid, os.WNOHANG)
            except ChildProcessError: pass

    def test_concurrent_start_refuses_second_broker(self):
        first = self.broker(); first.start()
        try:
            errors=[]
            def attempt():
                try: self.broker().start()
                except PrivilegedBrokerDenied as exc: errors.append(type(exc).__name__)
            threads=[threading.Thread(target=attempt) for _ in range(3)]
            for t in threads: t.start()
            for t in threads: t.join(timeout=3)
            self.assertTrue(all(not t.is_alive() for t in threads))
            self.assertEqual(errors, ['PrivilegedBrokerDenied']*3)
        finally: first.close()

    @unittest.skipUnless(hasattr(os, 'fork'), 'requires POSIX fork')
    def test_real_concurrent_startup_processes(self):
        start_r, start_w = os.pipe()
        result_r, result_w = os.pipe()
        pids = []
        for _ in range(2):
            pid = os.fork()
            if pid == 0:
                os.close(start_w); os.close(result_r)
                os.read(start_r, 1)
                try:
                    broker = self.broker()
                    broker.start()
                    os.write(result_w, b'S')
                    signal.pause()
                except PrivilegedBrokerDenied:
                    os.write(result_w, b'B')
                os._exit(0)
            pids.append(pid)
        os.close(start_r); os.close(result_w)
        try:
            os.write(start_w, b'XX')
            # Each process must report before the winning service is killed.
            outcomes = os.read(result_r, 1) + os.read(result_r, 1)
            self.assertEqual(sorted(outcomes), sorted(b'BS'))
        finally:
            for pid in pids:
                try: os.kill(pid, signal.SIGKILL)
                except ProcessLookupError: pass
            for pid in pids:
                try: os.waitpid(pid, 0)
                except ChildProcessError: pass
            os.close(start_w); os.close(result_r)
            path = self.ipc/'recovery-v011.sock'
            if path.exists() or path.is_socket(): path.unlink()

    def test_tampered_transport_group_refused(self):
        if os.geteuid() != 0: self.skipTest('requires chown privilege')
        os.chown(self.ipc, os.geteuid(), self.gid + 1)
        with self.assertRaises(PrivilegedBrokerDenied): self.broker()

    @unittest.skipUnless(hasattr(os, 'fork'), 'requires POSIX fork')
    def test_sigkill_lifecycle_lock_released(self):
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            from railsystem.anchored_admission import _locked
            with _locked(self.state):
                os.write(write_fd, b'LOCKED')
                signal.pause()
            os._exit(0)
        os.close(write_fd)
        try:
            self.assertEqual(os.read(read_fd, 6), b'LOCKED')
            os.kill(pid, signal.SIGKILL)
            self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]), -signal.SIGKILL)
            from railsystem.anchored_admission import _locked
            with _locked(self.state): pass
        finally:
            os.close(read_fd)
            try: os.waitpid(pid, os.WNOHANG)
            except ChildProcessError: pass


if __name__ == '__main__': unittest.main()
