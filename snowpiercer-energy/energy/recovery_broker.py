"""ENERGY-CORE-009: simulation-only recovery broker, not a hardware trust root.

Permits are deliberately process-local and lost after a restart. Peer UID comes
from the kernel, never from client-supplied JSON. Broker is a single-process
IPC facade around the unified advisory lock; legacy direct writes remain possible.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import socket
import stat
import threading
from .admission import UnifiedEnergyAdmission
from .ipc import MAX_REQUEST, peer_uid
from .trust import AdmissionDenied

@dataclass(frozen=True)
class BrokerPermit:
    token: str
    uid: int
    sequence: int
    digest: str

class CrossUIDRecoveryBroker:
    def __init__(self, admission: UnifiedEnergyAdmission, path, allowed_uids):
        if not isinstance(admission, UnifiedEnergyAdmission):
            raise AdmissionDenied('unified admission required')
        self.admission = admission
        self.path = Path(path)
        self.allowed_uids = frozenset(allowed_uids)
        if not self.allowed_uids or any(type(u) is not int or u < 0 for u in self.allowed_uids):
            raise AdmissionDenied('invalid UID allowlist')
        parent = self.path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid() or parent.st_mode & 0o077:
            raise AdmissionDenied('private broker directory required')
        if self.path.is_symlink() or self.path.exists():
            raise AdmissionDenied('broker socket path occupied')
        self._permits = {}
        self._mutex = threading.RLock()
        self._pid = os.getpid()
        self.sock = None
        self._inode = None

    def _check_pid(self):
        if os.getpid() != self._pid:
            raise AdmissionDenied('forked broker forbidden')

    def _check_socket(self):
        st = self.path.lstat()
        if not stat.S_ISSOCK(st.st_mode) or (st.st_dev, st.st_ino) != self._inode or st.st_uid != os.geteuid():
            raise AdmissionDenied('broker socket substituted')

    def __enter__(self):
        self._check_pid()
        with self.admission.locked():
            self.admission.gateway.snapshot()
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(str(self.path))
                os.chmod(self.path, 0o600)
                sock.listen(16)
                st = self.path.lstat()
                self._inode = (st.st_dev, st.st_ino)
                self.sock = sock
            except BaseException:
                sock.close()
                raise
        return self

    def __exit__(self, *args):
        if self.sock:
            self.sock.close()
            self.sock = None
        try:
            self._check_socket()
            self.path.unlink()
        except (FileNotFoundError, AdmissionDenied):
            pass
        self._permits.clear()

    def issue(self, uid):
        self._check_pid()
        if uid not in self.allowed_uids:
            raise AdmissionDenied('UID denied')
        with self._mutex, self.admission.locked():
            seq, digest, _ = self.admission.gateway.snapshot()
            permit = BrokerPermit(secrets.token_hex(32), uid, seq, digest)
            self._permits[permit.token] = permit
            return permit

    def recover(self, uid, token):
        self._check_pid()
        with self._mutex, self.admission.locked():
            permit = self._permits.pop(token, None) if type(token) is str else None
            if permit is None or permit.uid != uid or uid not in self.allowed_uids:
                raise AdmissionDenied('invalid, consumed or foreign recovery permit')
            seq, digest, _ = self.admission.gateway.snapshot()
            if (seq, digest) != (permit.sequence, permit.digest):
                raise AdmissionDenied('recovery head changed')
            return seq, digest

    def serve_one(self):
        self._check_pid()
        self._check_socket()
        if self.sock is None:
            raise AdmissionDenied('broker not running')
        conn, _ = self.sock.accept()
        with conn:
            conn.settimeout(5)
            try:
                self._check_socket()
                uid = peer_uid(conn)
                if uid not in self.allowed_uids:
                    raise AdmissionDenied('UID denied')
                raw = bytearray()
                while b'\n' not in raw:
                    part = conn.recv(min(4096, MAX_REQUEST + 1 - len(raw)))
                    if not part or len(raw) + len(part) > MAX_REQUEST:
                        raise AdmissionDenied('invalid framing')
                    raw.extend(part)
                if raw.count(b'\n') != 1 or not raw.endswith(b'\n'):
                    raise AdmissionDenied('invalid framing')
                req = json.loads(raw.decode('utf8'))
                if not isinstance(req, dict):
                    raise AdmissionDenied('invalid schema')
                if req == {'action':'issue'}:
                    permit = self.issue(uid)
                    response = {'ok':True,'token':permit.token,'sequence':permit.sequence,'digest':permit.digest}
                elif set(req) == {'action','token'} and req['action'] == 'recover':
                    seq, digest = self.recover(uid, req['token'])
                    response = {'ok':True,'sequence':seq,'digest':digest}
                else:
                    raise AdmissionDenied('unsupported action')
            except Exception as exc:
                response = {'ok':False,'error':type(exc).__name__}
            try:
                conn.sendall((json.dumps(response,sort_keys=True)+'\n').encode())
            except (BrokenPipeError,ConnectionResetError):
                pass

def broker_request(path, request):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
        conn.settimeout(5)
        conn.connect(str(path))
        conn.sendall((json.dumps(request,allow_nan=False)+'\n').encode())
        data = bytearray()
        while b'\n' not in data:
            part = conn.recv(4096)
            if not part or len(data)+len(part)>MAX_REQUEST:
                raise AdmissionDenied('invalid response')
            data.extend(part)
        return json.loads(data.decode('utf8'))
