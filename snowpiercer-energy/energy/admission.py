"""ENERGY-CORE-007: opt-in unified admission for simulation only.

Not an independent trust root. A same-UID writer or legacy direct ledger API
can bypass this module; production admission therefore remains BLOCKED.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import secrets
import stat
import threading
from .trust import AdmissionDenied, TrustedEnergyGateway


@dataclass(frozen=True)
class RecoveryPermit:
    token: str
    uid: int
    sequence: int
    digest: str


class UnifiedEnergyAdmission:
    """One advisory lock across startup, writes and cold recovery.

    Permits are process-local, single-use and UID-bound. They are not durable
    and deliberately cannot authorize cross-process or cross-UID recovery.
    """
    def __init__(self, gateway: TrustedEnergyGateway, lock_path):
        if not isinstance(gateway, TrustedEnergyGateway):
            raise AdmissionDenied('trusted gateway required')
        self.gateway = gateway
        self.lock_path = Path(lock_path)
        self._mutex = threading.RLock()
        self._permits = {}
        self._owner_pid = os.getpid()
        parent = self.lock_path.parent
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise AdmissionDenied('private lock directory required')
        if self.lock_path.is_symlink():
            raise AdmissionDenied('symlink lock forbidden')

    @contextmanager
    def locked(self):
        if os.getpid() != self._owner_pid:
            raise AdmissionDenied('inherited admission controller forbidden')
        with self._mutex:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            try:
                st = os.fstat(fd)
                if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1 or st.st_mode & 0o077:
                    raise AdmissionDenied('unsafe lock inode')
                fcntl.flock(fd, fcntl.LOCK_EX)
                current = self.lock_path.lstat()
                if (current.st_dev, current.st_ino) != (st.st_dev, st.st_ino):
                    raise AdmissionDenied('lock path replaced')
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def startup(self, fault_hook=None):
        with self.locked():
            if fault_hook: fault_hook('startup_lock')
            result = self.gateway.snapshot()
            if fault_hook: fault_hook('startup_verified')
            return result

    def apply(self, *args, fault_hook=None, **kwargs):
        with self.locked():
            if fault_hook: fault_hook('admission_lock')
            self.gateway.snapshot()
            if fault_hook: fault_hook('admission_verified')
            return self.gateway.apply(*args, fault_hook=fault_hook, **kwargs)

    def issue_recovery_permit(self, uid):
        if type(uid) is not int or uid != os.geteuid():
            raise AdmissionDenied('recovery UID mismatch')
        with self.locked():
            seq, digest, _ = self.gateway.snapshot()
            permit = RecoveryPermit(secrets.token_hex(32), uid, seq, digest)
            self._permits[permit.token] = permit
            return permit

    def cold_recover(self, permit: RecoveryPermit, uid, fault_hook=None):
        if type(uid) is not int or uid != os.geteuid() or not isinstance(permit, RecoveryPermit):
            raise AdmissionDenied('invalid recovery identity')
        with self.locked():
            stored = self._permits.pop(permit.token, None)
            if stored is None or stored != permit or stored.uid != uid:
                raise AdmissionDenied('recovery permit missing, altered or consumed')
            if fault_hook: fault_hook('recovery_lock')
            result = self.gateway.snapshot()
            if result[:2] != (stored.sequence, stored.digest):
                raise AdmissionDenied('recovery head changed')
            if fault_hook: fault_hook('recovery_verified')
            return result
