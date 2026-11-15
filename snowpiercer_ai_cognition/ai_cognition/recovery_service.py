"""AI-CORE-010: fail-closed restart boundary for a cross-UID admission service.

No automatic audit checkpoint reconciliation is permitted. The caller must create
fresh store/manager/gateway objects after each crash. Privilege drop is external.
"""
import errno
import os
import socket
import stat
from pathlib import Path
from .cross_uid import CrossUIDAdmissionService, verify_cross_uid_layout
from .lifecycle import RecoveryRequired
from .service_identity import IsolationError


def reclaim_stale_socket(path, *, service_uid, socket_dir):
    """Reclaim a dead Unix socket only in a private, verified directory.

    Not safe against another privileged writer sharing the directory; production
    deployments must ensure exclusive directory ownership and supervision.
    """
    path = Path(path)
    directory = Path(socket_dir)
    if path.parent.absolute() != directory.absolute():
        raise IsolationError('SOCKET_PATH_INVALID')
    d = directory.lstat()
    if not stat.S_ISDIR(d.st_mode) or d.st_uid != service_uid or stat.S_IMODE(d.st_mode) != 0o710:
        raise IsolationError('UNSAFE_SOCKET_DIRECTORY')
    try:
        entry = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISSOCK(entry.st_mode) or entry.st_uid != service_uid or entry.st_nlink != 1:
        raise IsolationError('SOCKET_REPLACEMENT_DETECTED')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        try:
            probe.connect(str(path))
        except OSError as exc:
            if exc.errno not in (errno.ECONNREFUSED,):
                raise IsolationError('SOCKET_STATE_UNCERTAIN') from exc
        else:
            raise IsolationError('SOCKET_ALREADY_ACTIVE')
    # Revalidate inode to detect replacement between probe and unlink.
    current = path.lstat()
    if (current.st_dev, current.st_ino) != (entry.st_dev, entry.st_ino):
        raise IsolationError('SOCKET_REPLACEMENT_DETECTED')
    path.unlink()
    return True


class RecoverableCrossUIDService(CrossUIDAdmissionService):
    """Strict startup: verify state before exposing IPC; never auto-reconcile."""
    def __init__(self, gateway, socket_path, *, private_dir, socket_dir,
                 service_uid, ipc_gid, allowed_uids, recovery_secret,
                 recovery_uids=()):
        if os.geteuid() != service_uid or service_uid == 0:
            raise IsolationError('SERVICE_UID_REQUIRED')
        # Validate private data and trusted audit before touching a stale socket.
        gateway.verify()
        reclaim_stale_socket(socket_path, service_uid=service_uid, socket_dir=socket_dir)
        super().__init__(gateway, socket_path, private_dir=private_dir,
                         socket_dir=socket_dir, service_uid=service_uid,
                         ipc_gid=ipc_gid, allowed_uids=allowed_uids,
                         recovery_secret=recovery_secret, recovery_uids=recovery_uids)

    def serve(self, *, ready=None):
        self.gateway.verify()
        return super().serve(ready=ready)


def production_gateway_only(*, gateway, service_uid):
    """Reject unisolated gateway for production entrypoint registration."""
    if service_uid == 0 or os.geteuid() != service_uid:
        raise IsolationError('SERVICE_UID_REQUIRED')
    gateway.verify()
    return True
