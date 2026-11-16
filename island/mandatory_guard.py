"""ISLAND-GEO-019: opt-in hardened production entrypoint.

The OS owner of the service database must be the service UID. This module does
not (and cannot) prevent a process with that UID from importing legacy APIs.
"""
import fcntl
import os
import socket
import stat
from contextlib import contextmanager
from pathlib import Path
from .anchored_admission import AdmissionDenied
from .socket_isolation import IsolatedProductionServer
from .production_guard import inspect_endpoint, assert_endpoint_unchanged, verify_storage_owner
from .production_admission import peer_uid


def _private_regular(path, uid):
    path = Path(path)
    try:
        st = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(st.st_mode) or st.st_uid != uid or st.st_nlink != 1 or st.st_mode & 0o077:
        raise AdmissionDenied('private file compromised: ' + str(path))
    return True


def _safe_existing(path, uid):
    for suffix in ('', '-journal', '-wal', '-shm'):
        _private_regular(str(path) + suffix, uid)


@contextmanager
def startup_lease(lock_path):
    """Exclusive, nonblocking service lifetime lease; rejects lock replacement."""
    lock_path = Path(lock_path)
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(lock_path, flags, 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.geteuid() or st.st_mode & 0o077:
            raise AdmissionDenied('unsafe startup lock')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AdmissionDenied('concurrent production startup') from exc
        current = lock_path.lstat()
        if (current.st_dev, current.st_ino) != (st.st_dev, st.st_ino):
            raise AdmissionDenied('startup lock substituted')
        yield
    finally:
        os.close(fd)


class MandatoryGuardServer(IsolatedProductionServer):
    """Guard integrated into production startup; requires independent OS provisioning."""
    def _preflight(self):
        super()._preflight()
        uid = os.geteuid()
        _safe_existing(self.db, uid)
        _safe_existing(self.db.with_suffix('.lock'), uid)
        # Private authority database is inaccessible to the service by design.
        # Verify socket identity before sending a recovery token.
        self._authority_identity = inspect_endpoint(
            self.authority, owner=self.witness_uid,
            group=self.authority.stat().st_gid, directory=self.authority.parent)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
            peer.settimeout(3)
            peer.connect(str(self.authority))
            if peer_uid(peer) != self.witness_uid:
                raise AdmissionDenied('authority kernel peer UID mismatch')
        assert_endpoint_unchanged(self.authority, self._authority_identity)

    def serve(self, limit=None, recovery_token=None):
        if recovery_token is None:
            raise AdmissionDenied('mandatory recovery token missing')
        with startup_lease(self.db.parent / '.production-startup.lock'):
            return super().serve(limit=limit, recovery_token=recovery_token)
