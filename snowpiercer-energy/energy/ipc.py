"""Simulation-only UNIX IPC admission. Not a physical control plane.

Peer credentials are kernel supplied on Linux; unsupported systems fail closed.
"""
import json
import os
from pathlib import Path
import socket
import stat
import struct
from .trust import AdmissionDenied, TrustedEnergyGateway
from .domain import PowerRequest
from .accounting import StorageDispatch

MAX_REQUEST = 65536


def peer_uid(conn):
    if not hasattr(socket, 'SO_PEERCRED'):
        raise AdmissionDenied('kernel peer credentials unavailable')
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
    pid, uid, gid = struct.unpack('3i', raw)
    if pid <= 0 or uid < 0:
        raise AdmissionDenied('invalid peer credentials')
    return uid


class EnergyIPCServer:
    """Single-process admission service; only configured UIDs may submit simulations.

    Socket directory must be privately owned; no socket replacement is attempted.
    Does not protect against a compromised same-UID process or direct ledger access.
    """
    def __init__(self, gateway: TrustedEnergyGateway, path, allowed_uids):
        if not isinstance(gateway, TrustedEnergyGateway):
            raise AdmissionDenied('gateway required')
        self.gateway = gateway
        self.path = Path(path)
        self.allowed_uids = frozenset(allowed_uids)
        if not self.allowed_uids or any(type(uid) is not int or uid < 0 for uid in self.allowed_uids):
            raise AdmissionDenied('invalid UID allowlist')
        parent = self.path.parent
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise AdmissionDenied('socket directory must be private and owned by service')
        if self.path.is_symlink() or self.path.exists():
            raise AdmissionDenied('socket path occupied; refusing replacement')
        self.sock = None
        self._inode = None

    def __enter__(self):
        self.gateway.snapshot()  # fail closed before socket publication
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(self.path))
            os.chmod(self.path, 0o600)
            sock.listen(16)
            self._inode = self.path.lstat().st_ino
            self.sock = sock
            return self
        except BaseException:
            sock.close()
            raise

    def __exit__(self, *exc):
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        try:
            if self.path.lstat().st_ino == self._inode and stat.S_ISSOCK(self.path.lstat().st_mode):
                self.path.unlink()
        except FileNotFoundError:
            pass

    def serve_one(self):
        if self.sock is None:
            raise AdmissionDenied('server not running')
        with self.sock.accept()[0] as conn:
            conn.settimeout(5)
            try:
                if peer_uid(conn) not in self.allowed_uids:
                    raise AdmissionDenied('UID not authorized')
                raw = bytearray()
                while b'\n' not in raw:
                    part = conn.recv(min(4096, MAX_REQUEST + 1 - len(raw)))
                    if not part or len(raw) + len(part) > MAX_REQUEST:
                        raise AdmissionDenied('request size or framing invalid')
                    raw.extend(part)
                if raw.count(b'\n') != 1 or not raw.endswith(b'\n'):
                    raise AdmissionDenied('trailing request bytes')
                request = json.loads(raw.decode('utf8'))
                if not isinstance(request, dict) or set(request) != {'action', 'operation_id', 'requests', 'duration_h', 'dispatch', 'reserve_kw', 'expected_sequence'}:
                    raise AdmissionDenied('invalid request schema')
                if request['action'] != 'simulate':
                    raise AdmissionDenied('hardware/legacy action denied')
                result = self.gateway.apply(request['operation_id'],
                    [PowerRequest(*r) for r in request['requests']],
                    duration_h=request['duration_h'],
                    dispatch=[StorageDispatch(*d) for d in request['dispatch']],
                    reserve_kw=request['reserve_kw'], expected_sequence=request['expected_sequence'])
                response = {'ok': True, 'sequence': result.sequence, 'digest': result.digest}
            except Exception as exc:
                response = {'ok': False, 'error': type(exc).__name__}
            try:
                conn.sendall((json.dumps(response, sort_keys=True) + '\n').encode())
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # client disconnected; never retry an already applied operation


def submit_simulation(path, request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(5)
        conn.connect(str(path))
        try:
            conn.sendall((json.dumps(request, allow_nan=False) + '\n').encode())
        except BrokenPipeError:
            return {'ok': False, 'error': 'ConnectionClosed'}
        response = bytearray()
        while b'\n' not in response:
            part = conn.recv(4096)
            if not part or len(response) + len(part) > MAX_REQUEST:
                raise AdmissionDenied('invalid response')
            response.extend(part)
        return json.loads(response.decode())
