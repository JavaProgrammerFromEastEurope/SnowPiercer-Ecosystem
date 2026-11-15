"""AI-CORE-009: opt-in Linux cross-UID socket access and restart supervision.

Administrator must provision a dedicated service UID and a shared IPC GID.
Private state is never placed under the traversable IPC directory.
"""
import os
import stat
import time
from pathlib import Path
from .service_identity import IsolationError, verify_runtime_identity
from .isolation import AdmissionIPCServer


def verify_cross_uid_layout(private_dir, socket_dir, *, service_uid, ipc_gid):
    if service_uid == 0 or os.geteuid() != service_uid:
        raise IsolationError('SERVICE_UID_REQUIRED')
    private, public = Path(private_dir), Path(socket_dir)
    if private.resolve() == public.resolve():
        raise IsolationError('DIRECTORY_SEPARATION_REQUIRED')
    for path, mode, gid in ((private, 0o700, None), (public, 0o710, ipc_gid)):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != service_uid or stat.S_IMODE(info.st_mode) != mode:
            raise IsolationError('UNSAFE_DIRECTORY')
        if gid is not None and info.st_gid != gid:
            raise IsolationError('IPC_GROUP_MISMATCH')
    for item in private.iterdir():
        info = item.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != service_uid or stat.S_IMODE(info.st_mode) != 0o600:
            raise IsolationError('UNSAFE_PRIVATE_ENTRY')
    for item in public.iterdir():
        raise IsolationError('SOCKET_DIRECTORY_NOT_EMPTY')
    return True


class CrossUIDAdmissionService(AdmissionIPCServer):
    """Separate-UID service; socket group controls access, peer UID policy still applies."""
    def __init__(self, gateway, socket_path, *, private_dir, socket_dir, service_uid,
                 ipc_gid, allowed_uids, recovery_secret, recovery_uids=()):
        self.private_dir = Path(private_dir)
        self.socket_dir = Path(socket_dir)
        self.service_uid = service_uid
        self.ipc_gid = ipc_gid
        path = Path(socket_path)
        if path.parent.absolute() != self.socket_dir.absolute():
            raise IsolationError('SOCKET_PATH_INVALID')
        verify_cross_uid_layout(private_dir, socket_dir, service_uid=service_uid, ipc_gid=ipc_gid)
        super().__init__(gateway, path, allowed_uids=allowed_uids,
                         recovery_secret=recovery_secret, recovery_uids=recovery_uids)
        self.socket_mode = 0o660
        self.socket_gid = ipc_gid

    def serve(self, *, ready=None):
        verify_cross_uid_layout(self.private_dir, self.socket_dir,
                                service_uid=self.service_uid, ipc_gid=self.ipc_gid)
        return super().serve(ready=ready)


def supervise_process(factory, *, stop_event, max_restarts=3, delay=0.05):
    """Supervisor loop; factory creates a new child Process on every attempt.

    No restart after normal exit; exhaustion fails closed. OS service manager
    remains responsible for restarting the supervisor itself.
    """
    restarts = 0
    while not stop_event.is_set():
        child = factory()
        child.start()
        child.join()
        if child.exitcode == 0:
            return restarts
        if stop_event.is_set():
            return restarts
        if restarts >= max_restarts:
            raise RuntimeError('RESTART_BUDGET_EXHAUSTED')
        restarts += 1
        time.sleep(delay)
    return restarts
