"""AI-CORE-020: shared nonblocking process lock for service and recovery.

Advisory locks require all trusted writers to participate. No cross-host fencing.
"""
import fcntl
import os
import stat
from pathlib import Path
from .lifecycle import RecoveryRequired
from .service_identity import IsolationError


def acquire_runtime_lock(private):
    private = Path(private)
    st = private.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        raise IsolationError('UNSAFE_LOCK_DIRECTORY')
    path = private / 'recovery016.lock'  # preserve existing cold-recovery lock identity
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0), 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1:
            raise IsolationError('UNSAFE_RECOVERY_LOCK')
        if path.lstat().st_ino != st.st_ino or path.lstat().st_dev != st.st_dev:
            raise IsolationError('RECOVERY_LOCK_REPLACED')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RecoveryRequired('RECOVERY_ALREADY_IN_PROGRESS') from exc
        # Lock pathname must still identify the inode we locked.
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (st.st_dev, st.st_ino):
            raise IsolationError('RECOVERY_LOCK_REPLACED')
        return fd
    except BaseException:
        os.close(fd)
        raise


def release_runtime_lock(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
