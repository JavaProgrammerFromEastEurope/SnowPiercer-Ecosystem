"""ISLAND-GEO-022: 3 separate ownership domains for root/witness/permit authority.

SoftwareRootServer is a lab fixture; lack of independent monotonic hardware root
must block production admission. No shared SQLite files or signing keys.
"""
import os
import signal
import socket
import sqlite3
import stat
from pathlib import Path

from .anchored_admission import AdmissionDenied, WitnessStore, _receive, _send
from .bound_ipc import PinnedBoundAuthorityClient
from .bound_recovery import BoundPermitAuthority
from .production_admission import peer_uid, secure_directory
from .mandatory_guard import _safe_existing
from .monotonic_root import RootClient
from .attested_broker import AttestedWriteBroker


def _private_layout(endpoint, db):
    uid = os.geteuid()
    if uid == 0:
        raise AdmissionDenied('root UID prohibited for role')
    secure_directory(Path(db).parent, uid)
    for p in (Path(db), Path(db).with_suffix('.lock'), Path(str(db)+'-wal'),
              Path(str(db)+'-shm'), Path(str(db)+'-journal')):
        _safe_existing(p, uid)
    endpoint = Path(endpoint)
    namespace = endpoint.parent.lstat()
    if (not stat.S_ISDIR(namespace.st_mode) or namespace.st_uid != 0
            or not namespace.st_mode & stat.S_ISVTX
            or namespace.st_mode & 0o777 != 0o777):
        raise AdmissionDenied('root-owned sticky IPC namespace required')
    if endpoint.exists() or endpoint.is_symlink():
        raise AdmissionDenied('occupied endpoint')
    return endpoint


def _serve_loop(endpoint, fn):
    endpoint = Path(endpoint)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(endpoint))
        os.chmod(endpoint, 0o660)
        server.listen(16)
        server.settimeout(.25)
        try:
            while True:
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                with conn:
                    conn.settimeout(3)
                    try:
                        uid = peer_uid(conn)
                        request = _receive(conn)
                        result = fn(uid, request)
                        _send(conn, {'ok': True, 'result': result})
                    except (AdmissionDenied, KeyError, ValueError, sqlite3.Error, OSError) as exc:
                        try:
                            _send(conn, {'ok': False, 'reason': str(exc)})
                        except OSError:
                            pass
        finally:
            if endpoint.is_socket() and endpoint.stat().st_uid == os.geteuid():
                endpoint.unlink()


class SplitWitnessServer:
    """Witness UID exclusively controls its SQLite; root protocol is separate UID.

    A crash after witness CAS but before remote root CAS leaves the system
    fail-closed until independent offline intervention (never auto-heal).
    """
    POINTS = ('before_witness_cas', 'after_witness_cas', 'before_root_cas',
              'after_root_cas', 'before_witness_reply')

    def __init__(self, endpoint, db, root_endpoint, root_uid, root_public_key,
                 broker_uid, permit_uid, crash_at=None):
        values = (os.geteuid(), root_uid, broker_uid, permit_uid)
        if any(type(i) is not int or i <= 0 for i in values) or len(set(values)) != 4:
            raise AdmissionDenied('witness/root/broker/permit UID must be separate')
        if crash_at not in (None, *self.POINTS):
            raise AdmissionDenied('bad witness crash point')
        self.endpoint = endpoint
        self.db = db
        self.root = RootClient(root_endpoint, root_uid, root_public_key)
        self.broker_uid, self.permit_uid = broker_uid, permit_uid
        self.crash_at = crash_at

    def _kill(self, point):
        if self.crash_at == point:
            os.kill(os.getpid(), signal.SIGKILL)

    def serve(self):
        _private_layout(self.endpoint, self.db)
        store = WitnessStore(self.db)
        head = store.execute('read')
        self.root.require_head(head)  # Strictly no socket publication on rollback.

        def handle(uid, request):
            if type(request) is not dict or set(request) != {'operation', 'record', 'token'}:
                raise AdmissionDenied('invalid witness request')
            operation = request['operation']
            if operation == 'read':
                if uid not in (self.broker_uid, self.permit_uid):
                    raise AdmissionDenied('witness read UID mismatch')
                head = store.execute('read')
                self.root.require_head(head)
                return head
            if operation != 'cas' or uid != self.broker_uid:
                raise AdmissionDenied('witness CAS UID mismatch')
            previous = store.execute('read')
            self.root.require_head(previous)
            self._kill('before_witness_cas')
            advanced = store.execute('cas', request['record'])
            self._kill('after_witness_cas')
            self._kill('before_root_cas')
            # Root CAS is monotonic in the fixture, but not independently protected.
            if advanced != previous:
                self.root.execute('cas', request['record'])
            self._kill('after_root_cas')
            self.root.require_head(advanced)
            self._kill('before_witness_reply')
            return advanced

        _serve_loop(self.endpoint, handle)


class SplitPermitServer:
    """Separate nonroot permit UID. Witness is read only, UID-pinned."""
    POINTS = ('before_permit_issue', 'after_permit_issue',
              'before_permit_consume', 'after_permit_consume')

    def __init__(self, endpoint, db, witness_endpoint, witness_uid, broker_uid, client_uid, crash_at=None):
        values = (os.geteuid(), witness_uid, broker_uid, client_uid)
        if any(type(i) is not int or i <= 0 for i in values) or len(set(values)) != 4:
            raise AdmissionDenied('permit/witness/broker/client UID must be separate')
        if crash_at not in (None, *self.POINTS):
            raise AdmissionDenied('unknown permit crash point')
        self.endpoint, self.db, self.witness_endpoint = endpoint, db, witness_endpoint
        self.witness_uid, self.broker_uid, self.client_uid = witness_uid, broker_uid, client_uid
        self.crash_at = crash_at

    def _kill(self, point):
        if self.crash_at == point:
            os.kill(os.getpid(), signal.SIGKILL)

    def serve(self):
        _private_layout(self.endpoint, self.db)
        witness = PinnedBoundAuthorityClient(self.witness_endpoint, self.witness_uid)
        witness.execute('read')
        permits = BoundPermitAuthority(self.db, self.client_uid, self.broker_uid, witness)

        def handle(uid, request):
            if type(request) is not dict or set(request) != {'operation', 'record', 'token'}:
                raise AdmissionDenied('invalid permit request')
            operation = request['operation']
            if operation == 'issue':
                self._kill('before_permit_issue')
                result = permits.execute(uid, 'issue')
                self._kill('after_permit_issue')
                return result
            if operation == 'consume':
                self._kill('before_permit_consume')
                result = permits.execute(uid, 'consume', request['token'])
                self._kill('after_permit_consume')
                return result
            raise AdmissionDenied('unsupported permit operation')

        _serve_loop(self.endpoint, handle)


class _SplitAuthorityClient:
    def __init__(self, witness_endpoint, witness_uid, permit_endpoint, permit_uid):
        self.witness = PinnedBoundAuthorityClient(str(witness_endpoint), witness_uid)
        self.permit = PinnedBoundAuthorityClient(str(permit_endpoint), permit_uid)
    def execute(self, operation, record=None, token=None):
        if operation in ('read', 'cas'):
            return self.witness.execute(operation, record=record)
        if operation == 'consume':
            return self.permit.execute(operation, token=token)
        raise AdmissionDenied('operation not supported by split authorities')


class SplitAttestedWriteBroker(AttestedWriteBroker):
    """Opt-in isolated broker; strict variant adds mandatory OS/hardware gate."""
    def __init__(self, socket_path, db_path, witness_endpoint, permit_endpoint,
                 public_key_path, client_uid, service_uid, witness_uid, permit_uid, crash_at=None):
        super().__init__(socket_path, db_path, witness_endpoint, public_key_path,
                         client_uid, service_uid, witness_uid, crash_at)
        if permit_uid in (client_uid, service_uid, witness_uid, os.geteuid()) or type(permit_uid) is not int or permit_uid <= 0:
            raise AdmissionDenied('independent permit UID mandatory')
        self.permit_endpoint = Path(permit_endpoint)
        self.permit_uid = permit_uid

    def preflight(self):
        super().preflight()
        if self.permit_endpoint.is_symlink() or not self.permit_endpoint.is_socket():
            raise AdmissionDenied('missing independent permit authority')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(3)
            conn.connect(str(self.permit_endpoint))
            if peer_uid(conn) != self.permit_uid:
                raise AdmissionDenied('permit authority peer UID mismatch')

    def _authority_client(self):
        return _SplitAuthorityClient(self.authority, self.witness_uid,
                                     self.permit_endpoint, self.permit_uid)
