"""ISLAND-GEO-010: opt-in hardened production profile, NOT OS security certification.
Existing library APIs intentionally remain callable; OS provisioning is mandatory.
"""
import os, stat, socket, struct, fcntl
from pathlib import Path
from contextlib import contextmanager
from .anchored_admission import AdmissionDenied, WitnessClient
from .production_admission import ProductionAdmissionServer, ProductionAdmissionClient


def check_private_directory(path, uid):
    p = Path(path)
    s = p.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != uid or (s.st_mode & 0o077):
        raise AdmissionDenied('directory must be private to expected UID')
    return p


def check_private_file(path, uid):
    p = Path(path)
    s = p.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != uid or s.st_nlink != 1 or (s.st_mode & 0o077):
        raise AdmissionDenied('file must be private, single-linked, and owned by expected UID')
    return p


def verify_peer(sock, expected_uid):
    if not hasattr(socket, 'SO_PEERCRED'):
        raise AdmissionDenied('peer credentials unavailable')
    uid = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
    if uid != expected_uid:
        raise AdmissionDenied('peer UID mismatch')
    return uid


class PinnedWitnessClient(WitnessClient):
    """Pins peer UID of the connected Unix socket, not just filesystem ownership."""
    def __init__(self, path, expected_uid):
        super().__init__(path)
        if type(expected_uid) is not int or expected_uid < 0:
            raise AdmissionDenied('invalid witness UID')
        self.expected_uid = expected_uid

    def execute(self, operation, record=None):
        from .anchored_admission import _send, _receive
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            sock.connect(self.path)
            verify_peer(sock, self.expected_uid)
            _send(sock, {'operation':operation, 'record':record})
            reply = _receive(sock)
            if type(reply) is not dict or reply.get('ok') is not True or type(reply.get('result')) is not dict:
                raise AdmissionDenied('witness rejected request or invalid response')
            return reply['result']


@contextmanager
def pinned_lock(path, uid):
    """Reject symlinks/hardlinks and inode substitution while lock is held."""
    p = Path(path)
    fd = os.open(str(p), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != uid or s.st_nlink != 1 or s.st_mode & 0o077:
            raise AdmissionDenied('unsafe lock file')
        fcntl.flock(fd, fcntl.LOCK_EX)
        current = p.lstat()
        if (current.st_dev, current.st_ino) != (s.st_dev, s.st_ino):
            raise AdmissionDenied('lock inode replaced')
        yield
        current = p.lstat()
        if (current.st_dev, current.st_ino) != (s.st_dev, s.st_ino):
            raise AdmissionDenied('lock inode replaced while held')
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


class HardenedProductionServer(ProductionAdmissionServer):
    """Strict opt-in profile. No claim of fencing untrusted legacy entrypoints."""
    def __init__(self, socket_path, local_db, witness_socket, client_uids, witness_uid, service_uid):
        super().__init__(socket_path, local_db, witness_socket, client_uids, witness_uid)
        self.service_uid = service_uid
        self.witness_client_factory = lambda path: PinnedWitnessClient(path, witness_uid)
        if type(service_uid) is not int or type(witness_uid) is not int or service_uid == witness_uid:
            raise AdmissionDenied('separate service/witness UIDs required')
        if service_uid in self.client_uids or witness_uid in self.client_uids:
            raise AdmissionDenied('client UID must be distinct')

    def _preflight(self):
        if os.geteuid() != self.service_uid:
            raise AdmissionDenied('service UID mismatch')
        check_private_directory(self.local_db.parent, self.service_uid)
        check_private_directory(self.socket_path.parent, self.service_uid)
        if self.local_db.exists():
            check_private_file(self.local_db, self.service_uid)
        lock = self.local_db.with_suffix('.lock')
        if lock.exists():
            check_private_file(lock, self.service_uid)
        for suffix in ('-journal','-wal','-shm'):
            aux = Path(str(self.local_db) + suffix)
            if aux.exists():
                check_private_file(aux, self.service_uid)
        return super()._preflight()

    def _preflight_runtime(self):
        self._preflight()


class PinnedProductionClient(ProductionAdmissionClient):
    def __init__(self, socket_path, service_uid):
        super().__init__(socket_path)
        self.service_uid = service_uid
        self.witness_client_factory = lambda path: PinnedWitnessClient(path, witness_uid)

    def admit(self, payload):
        from .anchored_admission import _send, _receive
        from .production_admission import MAX_PAYLOAD
        if type(payload) is not bytes or len(payload) > MAX_PAYLOAD:
            raise AdmissionDenied('invalid payload')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            sock.connect(self.socket_path)
            verify_peer(sock, self.service_uid)
            _send(sock, {'operation':'admit','payload':payload.hex()})
            response = _receive(sock)
            if type(response) is not dict or response.get('ok') is not True:
                raise AdmissionDenied('production admission denied')
            result = response.get('result')
            if type(result) is not dict or result.get('engineering_approval') != 'BLOCKED/NO-GO':
                raise AdmissionDenied('invalid readiness response')
            return result
