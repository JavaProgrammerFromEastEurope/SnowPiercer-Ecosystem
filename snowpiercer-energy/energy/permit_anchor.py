"""CORE-013 opt-in permit checkpoint. Local filesystem is NOT independent trust."""
import fcntl
from contextlib import contextmanager
import hashlib
import json
import os
import sqlite3
import stat
import tempfile
from contextlib import closing
from pathlib import Path
from .production_v3 import DurableEnergyService
from .trust import AdmissionDenied

class AnchoredDurableEnergyService(DurableEnergyService):
    """Fail-closed permit checkpoint for cooperative, simulation-only clients.

    A crash between SQLite commit and checkpoint update requires operator
    intervention; it never silently reauthorizes a consumed permit.
    """
    def __init__(self, admission, path, allowed_uids, permit_db, checkpoint_dir):
        self.checkpoint_dir = Path(checkpoint_dir)
        st = self.checkpoint_dir.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o077:
            raise AdmissionDenied('private checkpoint directory required')
        self.checkpoint = self.checkpoint_dir / 'permits.anchor'
        # Fail closed if checkpoint absent but permit database already exists.
        preexisting = Path(permit_db).exists()
        if preexisting and not self.checkpoint.exists():
            raise AdmissionDenied('checkpoint missing for existing permit database')
        super().__init__(admission, path, allowed_uids, permit_db)
        with self._mutex, self._checkpoint_locked():
            if preexisting:
                self._verify()
            else:
                self._write_checkpoint(self._fingerprint())

    @contextmanager
    def _checkpoint_locked(self):
        path = self.checkpoint_dir / 'permits.guard'
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            st = os.fstat(fd)
            if st.st_uid != os.geteuid() or st.st_nlink != 1 or st.st_mode & 0o077:
                raise AdmissionDenied('unsafe checkpoint guard')
            fcntl.flock(fd, fcntl.LOCK_EX)
            current = path.lstat()
            if (current.st_dev, current.st_ino) != (st.st_dev, st.st_ino):
                raise AdmissionDenied('checkpoint guard replaced')
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _fingerprint(self):
        with closing(self._open_permits()) as db:
            rows = db.execute('SELECT token,uid,sequence,digest,consumed FROM permits ORDER BY token').fetchall()
        payload = json.dumps(rows, separators=(',', ':'), ensure_ascii=True).encode()
        return hashlib.sha256(payload).hexdigest()

    def _verify(self):
        if self.checkpoint.is_symlink():
            raise AdmissionDenied('checkpoint symlink')
        fd = os.open(self.checkpoint, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1 or st.st_mode & 0o077 or st.st_size > 256:
                raise AdmissionDenied('unsafe checkpoint')
            with os.fdopen(fd, 'rb') as f:
                fd = -1
                stored = f.read().decode('ascii')
        finally:
            if fd >= 0: os.close(fd)
        if stored != self._fingerprint():
            raise AdmissionDenied('permit checkpoint mismatch: rollback or crash window')

    def _write_checkpoint(self, digest):
        fd, name = tempfile.mkstemp(prefix='.permit-', dir=self.checkpoint_dir)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(digest.encode('ascii'))
                f.flush(); os.fsync(f.fileno())
            os.replace(name, self.checkpoint)
            directory = os.open(self.checkpoint_dir, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if os.path.exists(name): os.unlink(name)

    def issue(self, uid):
        with self._mutex, self._checkpoint_locked():
            self._verify()
            permit = super().issue(uid)
            self._write_checkpoint(self._fingerprint())
            return permit

    def recover(self, uid, token):
        with self._mutex, self._checkpoint_locked():
            self._verify()
            try:
                return super().recover(uid, token)
            finally:
                # The permit may have committed even when recovery verification
                # failed. Advance checkpoint only for a verified DB; a crash
                # between these operations remains fail-closed on restart.
                self._write_checkpoint(self._fingerprint())
