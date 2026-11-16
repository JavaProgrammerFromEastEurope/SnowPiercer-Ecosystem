"""ISLAND-GEO-021: client-signed production admissions, verified by the write broker.

Linux SO_PEERCRED authenticates the forwarding facade; an Ed25519 signature
proves possession of the independently provisioned client key. Broker-owned
SQLite burns each nonce durably *before* witness CAS. A kill between nonce burn
and commit can lose availability, never permit an automatic replay. This does
not protect a compromised broker UID, root, or simultaneous ledger+witness rollback.
"""
import hashlib
import json
import os
import secrets
import signal
import socket
import sqlite3
import stat
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .anchored_admission import AdmissionDenied, _receive, _send
from .bound_ipc import PinnedBoundAuthorityClient
from .crash_protocol import CrashInstrumentedAdmission, POINTS
from .mandatory_guard import startup_lease, _safe_existing
from .production_admission import peer_uid
from .write_broker import WriteBroker, _identities

DOMAIN = b'ISLAND-GEO-021:CLIENT-ADMISSION:V1\0'
BROKER_POINTS = ('after_broker_ipc_read', 'before_nonce_commit', 'after_nonce_commit',
                 'after_broker_ipc_write')
ALL_CRASH_POINTS = POINTS + BROKER_POINTS


def _strict_hex(value, n):
    if type(value) is not str or len(value) != n or any(c not in '0123456789abcdef' for c in value):
        raise AdmissionDenied('noncanonical hex field')
    return bytes.fromhex(value)


def _canonical(message):
    return json.dumps(message, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def _message(payload, nonce, client_uid, broker_uid):
    if type(payload) is not bytes or not 1 <= len(payload) <= 4096:
        raise AdmissionDenied('invalid admission payload')
    _strict_hex(nonce, 32)
    for uid in (client_uid, broker_uid):
        if type(uid) is not int or uid <= 0:
            raise AdmissionDenied('nonroot identity required')
    if client_uid == broker_uid:
        raise AdmissionDenied('client and broker UID must differ')
    return {'protocol': 'ISLAND-GEO-021-v1', 'client_uid': client_uid,
            'broker_uid': broker_uid, 'nonce': nonce, 'payload': payload.hex()}


def sign_admission(payload, private_key_raw, client_uid, broker_uid, *, nonce=None):
    """Creates a canonical signed request; private_key_raw must remain client-owned."""
    if type(private_key_raw) is not bytes or len(private_key_raw) != 32:
        raise AdmissionDenied('Ed25519 private key must be 32 raw bytes')
    msg = _message(payload, secrets.token_hex(16) if nonce is None else nonce, client_uid, broker_uid)
    private = Ed25519PrivateKey.from_private_bytes(private_key_raw)
    return {'message': msg, 'signature': private.sign(DOMAIN + _canonical(msg)).hex()}


def verify_admission(envelope, public_key_raw, client_uid, broker_uid):
    if type(envelope) is not dict or set(envelope) != {'message', 'signature'}:
        raise AdmissionDenied('invalid signed envelope')
    message = envelope['message']
    if type(message) is not dict or set(message) != {'protocol', 'client_uid', 'broker_uid', 'nonce', 'payload'}:
        raise AdmissionDenied('invalid signed message')
    if message['protocol'] != 'ISLAND-GEO-021-v1' or type(message['client_uid']) is not int or type(message['broker_uid']) is not int:
        raise AdmissionDenied('signed protocol or identity mismatch')
    if message['client_uid'] != client_uid or message['broker_uid'] != broker_uid:
        raise AdmissionDenied('signed principal mismatch')
    nonce = message['nonce']
    _strict_hex(nonce, 32)
    payload = bytes.fromhex(message['payload']) if type(message['payload']) is str else None
    if payload is None or message != _message(payload, nonce, client_uid, broker_uid):
        raise AdmissionDenied('noncanonical signed payload')
    signature = _strict_hex(envelope['signature'], 128)
    if type(public_key_raw) is not bytes or len(public_key_raw) != 32:
        raise AdmissionDenied('invalid pinned public key')
    try:
        Ed25519PublicKey.from_public_bytes(public_key_raw).verify(signature, DOMAIN + _canonical(message))
    except (InvalidSignature, ValueError) as exc:
        raise AdmissionDenied('client signature rejected') from exc
    return payload, nonce


def _read_private_file(path, owner, n):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        pst = path.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != owner or st.st_nlink != 1
                or st.st_mode & 0o077 or (st.st_dev, st.st_ino) != (pst.st_dev, pst.st_ino)):
            raise AdmissionDenied('key file owner/mode/inode mismatch')
        value = os.read(fd, n + 1)
        if len(value) != n:
            raise AdmissionDenied('invalid key size')
        return value
    finally:
        os.close(fd)


def _kill_at(point, crash_at):
    if point == crash_at:
        os.kill(os.getpid(), signal.SIGKILL)


class AttestedWriteBroker(WriteBroker):
    """Broker denies all unsigned writes and records signed nonces durably."""
    def __init__(self, socket_path, db_path, authority_path, public_key_path,
                 client_uid, service_uid, witness_uid, crash_at=None):
        super().__init__(socket_path, db_path, authority_path, client_uid, service_uid, witness_uid)
        if crash_at is not None and crash_at not in ALL_CRASH_POINTS:
            raise AdmissionDenied('invalid broker SIGKILL point')
        self.public_key_path = Path(public_key_path)
        self.crash_at = crash_at
        self.public_key = None

    def preflight(self):
        super().preflight()
        if self.public_key_path.parent.resolve() != self.db.parent.resolve():
            raise AdmissionDenied('public key must reside in broker private directory')
        self.public_key = _read_private_file(self.public_key_path, os.geteuid(), 32)

    def _burn_nonce(self, nonce, envelope):
        """Fail-closed at the cost of losing requests killed after reservation."""
        db = sqlite3.connect(self.db, timeout=5, isolation_level=None)
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA journal_mode=DELETE')
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('CREATE TABLE IF NOT EXISTS signed_nonces '
                           '(client_uid INTEGER NOT NULL, nonce TEXT NOT NULL, '
                           'envelope_digest TEXT NOT NULL, PRIMARY KEY(client_uid,nonce))')
                db.execute('INSERT INTO signed_nonces VALUES (?,?,?)',
                           (self.client_uid, nonce, hashlib.sha256(_canonical(envelope)).hexdigest()))
                _kill_at('before_nonce_commit', self.crash_at)
                db.execute('COMMIT')
            except sqlite3.IntegrityError as exc:
                if db.in_transaction: db.execute('ROLLBACK')
                raise AdmissionDenied('signed request replay') from exc
            except BaseException:
                if db.in_transaction: db.execute('ROLLBACK')
                raise
        finally:
            db.close()
        _kill_at('after_nonce_commit', self.crash_at)

    def _authority_client(self):
        return PinnedBoundAuthorityClient(str(self.authority), self.witness_uid)

    def serve(self, recovery_token, limit=None):
        if type(recovery_token) is not str or not recovery_token:
            raise AdmissionDenied('mandatory state-bound recovery token')
        with startup_lease(self.db.parent / '.broker-startup.lock'):
            self.preflight()
            authority = self._authority_client()
            authority.execute('consume', token=recovery_token)
            admission = CrashInstrumentedAdmission(self.db, authority)
            admission.recover()  # Must reconcile before publishing the IPC endpoint.
            os.chmod(self.db, 0o600)
            os.chmod(self.db.with_suffix('.lock'), 0o600)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
                srv.bind(str(self.path))
                os.chmod(self.path, 0o660)
                srv.listen(16)
                srv.settimeout(.25)
                count = 0
                try:
                    while limit is None or count < limit:
                        try:
                            conn, _ = srv.accept()
                        except socket.timeout:
                            continue
                        count += 1
                        with conn:
                            conn.settimeout(3)
                            try:
                                if peer_uid(conn) != self.service_uid:
                                    raise AdmissionDenied('untrusted forwarding service UID')
                                request = _receive(conn)
                                _kill_at('after_broker_ipc_read', self.crash_at)
                                if type(request) is not dict or set(request) != {'operation', 'envelope'} or request['operation'] != 'admit_signed':
                                    raise AdmissionDenied('signed admission required')
                                payload, nonce = verify_admission(request['envelope'], self.public_key,
                                                                  self.client_uid, os.geteuid())
                                self._burn_nonce(nonce, request['envelope'])
                                result = admission.admit(payload, crash_at=self.crash_at if self.crash_at in POINTS else None)
                                _send(conn, {'ok': True, 'result': result})
                                _kill_at('after_broker_ipc_write', self.crash_at)
                            except (AdmissionDenied, ValueError, sqlite3.Error, OSError, KeyError) as exc:
                                try:
                                    _send(conn, {'ok': False, 'reason': str(exc)})
                                except OSError:
                                    pass
                finally:
                    if self.path.is_socket() and self.path.stat().st_uid == os.geteuid():
                        self.path.unlink()


class AttestedBrokerClient:
    def __init__(self, broker_socket, broker_uid):
        self.path = str(broker_socket)
        self.broker_uid = broker_uid

    def admit(self, envelope):
        if type(envelope) is not dict:
            raise AdmissionDenied('signed envelope required')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            sock.connect(self.path)
            if peer_uid(sock) != self.broker_uid:
                raise AdmissionDenied('broker kernel UID mismatch')
            _send(sock, {'operation': 'admit_signed', 'envelope': envelope})
            response = _receive(sock)
            if type(response) is not dict or response.get('ok') is not True:
                raise AdmissionDenied(response.get('reason', 'broker rejected') if type(response) is dict else 'bad broker reply')
            return response['result']


class AttestedAdmissionFacade:
    """Facade forwards a client-signed envelope but cannot authorize its own data."""
    def __init__(self, socket_path, broker_path, client_uid, broker_uid, witness_uid):
        self.path = Path(socket_path)
        self.broker_path = str(broker_path)
        self.client_uid = client_uid
        self.broker_uid = broker_uid
        _identities(client_uid, os.geteuid(), broker_uid, witness_uid)

    def serve(self, limit=None):
        if self.path.exists() or self.path.is_symlink():
            raise AdmissionDenied('occupied facade endpoint')
        broker = AttestedBrokerClient(self.broker_path, self.broker_uid)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
            srv.bind(str(self.path))
            os.chmod(self.path, 0o660)
            srv.listen(16)
            srv.settimeout(.25)
            count = 0
            try:
                while limit is None or count < limit:
                    try:
                        client, _ = srv.accept()
                    except socket.timeout:
                        continue
                    count += 1
                    with client:
                        client.settimeout(3)
                        try:
                            if peer_uid(client) != self.client_uid:
                                raise AdmissionDenied('client kernel UID mismatch')
                            request = _receive(client)
                            if type(request) is not dict or set(request) != {'operation', 'envelope'} or request['operation'] != 'admit_signed':
                                raise AdmissionDenied('signed client request required')
                            result = broker.admit(request['envelope'])
                            _send(client, {'ok': True, 'result': result})
                        except (AdmissionDenied, ValueError, OSError, sqlite3.Error) as exc:
                            try:
                                _send(client, {'ok': False, 'reason': str(exc)})
                            except OSError:
                                pass
            finally:
                if self.path.is_socket() and self.path.stat().st_uid == os.geteuid():
                    self.path.unlink()


class SignedAdmissionClient:
    """Client performs UID pinning of facade before disclosing signed requests."""
    def __init__(self, socket_path, facade_uid):
        self.path = str(socket_path)
        self.facade_uid = facade_uid

    def admit(self, envelope):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            sock.connect(self.path)
            if peer_uid(sock) != self.facade_uid:
                raise AdmissionDenied('facade kernel UID mismatch')
            _send(sock, {'operation': 'admit_signed', 'envelope': envelope})
            reply = _receive(sock)
            if type(reply) is not dict or reply.get('ok') is not True:
                raise AdmissionDenied(reply.get('reason', 'facade denied') if type(reply) is dict else 'bad facade response')
            return reply['result']
