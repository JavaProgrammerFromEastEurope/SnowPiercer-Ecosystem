"""ENERGY-CORE-019: bounded accept and process-level diagnostic primitives.

These primitives do not confer production authority. Linux SO_PEERCRED is
required for authentication; service ownership is enforced by OS provisioning.
"""
import os
import select
import socket
import stat
import time
from pathlib import Path
from .ipc import peer_uid
from .trust import AdmissionDenied


class AcceptDeadlineExceeded(AdmissionDenied):
    pass


def bounded_accept(listener, timeout_s=3.0):
    if not isinstance(timeout_s, (int, float)) or not 0 < timeout_s <= 60:
        raise AdmissionDenied('invalid accept timeout')
    deadline = time.monotonic() + timeout_s
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AcceptDeadlineExceeded('no IPC connection before deadline')
        ready, _, _ = select.select([listener], [], [], remaining)
        if ready:
            return listener.accept()


def assert_private_production_objects(paths, uid):
    """Fail closed on missing, symlink, hardlink, foreign-owner or permissive files."""
    if os.geteuid() != uid or os.getuid() != uid or uid == 0:
        raise AdmissionDenied('dedicated unprivileged service UID required')
    for raw in paths:
        p = Path(raw)
        if '..' in p.parts:
            raise AdmissionDenied('noncanonical production path')
        st = p.lstat()
        if st.st_uid != uid or st.st_mode & 0o077:
            raise AdmissionDenied('unsafe production object')
        if stat.S_ISREG(st.st_mode):
            if st.st_nlink != 1:
                raise AdmissionDenied('hardlinked production file')
        elif not stat.S_ISDIR(st.st_mode):
            raise AdmissionDenied('unsupported production object')


def authenticated_peer(conn, allowed_uids):
    uid = peer_uid(conn)
    if uid not in allowed_uids:
        raise AdmissionDenied('kernel-authenticated UID denied')
    return uid


def lock_diagnostics(lock_path):
    """Read-only local diagnostics; not a distributed lock ownership proof."""
    p = Path(lock_path)
    try:
        st = p.lstat()
        return {'exists': True, 'dev': st.st_dev, 'inode': st.st_ino,
                'uid': st.st_uid, 'mode': stat.S_IMODE(st.st_mode),
                'pid': os.getpid(), 'monotonic_ns': time.monotonic_ns()}
    except FileNotFoundError:
        return {'exists': False, 'pid': os.getpid(),
                'monotonic_ns': time.monotonic_ns()}
