"""AI-CORE-008: fail-closed Linux service filesystem boundary helpers.

Provision as administrator before dropping privileges. This module cannot
constrain a privileged process or another process running under the service UID.
"""
import os
import stat
from pathlib import Path

class IsolationError(RuntimeError):
    pass

def _directory(path, uid, mode):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise IsolationError('UNSAFE_DIRECTORY')
    info = path.stat()
    if info.st_uid != uid or stat.S_IMODE(info.st_mode) != mode:
        raise IsolationError('DIRECTORY_OWNER_OR_MODE')
    return path

def verify_service_layout(private_dir, socket_dir, *, service_uid=None):
    """Verify owned directories and all immediate private regular files.

    Reject symlinks, unexpected file types, group/other access and foreign owners.
    The caller must ensure parents are trusted and immutable to clients.
    """
    uid = os.geteuid() if service_uid is None else service_uid
    if type(uid) is not int or uid < 0:
        raise ValueError('service_uid')
    private = _directory(private_dir, uid, 0o700)
    sockets = _directory(socket_dir, uid, 0o700)
    if private.resolve() == sockets.resolve():
        raise IsolationError('DIRECTORY_SEPARATION_REQUIRED')
    for entry in private.iterdir():
        info = entry.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o600:
            raise IsolationError('UNSAFE_PRIVATE_ENTRY')
    for entry in sockets.iterdir():
        raise IsolationError('SOCKET_DIRECTORY_NOT_EMPTY')
    return True

def provision_service_layout(private_dir, socket_dir, *, service_uid=None, service_gid=None):
    """Provision empty directories, refusing symlinks or existing contents.

    Only call from a trusted administrative deployment step. No recursive chown.
    """
    uid = os.geteuid() if service_uid is None else service_uid
    gid = os.getegid() if service_gid is None else service_gid
    if type(uid) is not int or type(gid) is not int or uid < 0 or gid < 0:
        raise ValueError('identity')
    paths = [Path(private_dir), Path(socket_dir)]
    if paths[0].absolute() == paths[1].absolute():
        raise IsolationError('DIRECTORY_SEPARATION_REQUIRED')
    for path in paths:
        if path.is_symlink():
            raise IsolationError('SYMLINK_DENIED')
        if path.exists():
            if not path.is_dir() or any(path.iterdir()):
                raise IsolationError('NONEMPTY_OR_UNSAFE_DIRECTORY')
        else:
            path.mkdir(mode=0o700)
        os.chown(path, uid, gid)
        os.chmod(path, 0o700)
    return verify_service_layout(paths[0], paths[1], service_uid=uid)

def verify_runtime_identity(service_uid, private_dir, socket_dir):
    if os.geteuid() != service_uid or service_uid == 0:
        raise IsolationError('SERVICE_UID_REQUIRED')
    return verify_service_layout(private_dir, socket_dir, service_uid=service_uid)

class IsolatedAdmissionIPCServer:
    """Opt-in wrapper: verify service identity before binding an IPC socket."""
    def __init__(self, gateway, socket_path, *, service_uid, private_dir, socket_dir,
                 allowed_uids, recovery_secret, recovery_uids=()):
        from .isolation import AdmissionIPCServer
        self.service_uid = service_uid
        self.private_dir = Path(private_dir)
        self.socket_dir = Path(socket_dir)
        socket_path = Path(socket_path)
        if socket_path.parent.absolute() != self.socket_dir.absolute():
            raise IsolationError('SOCKET_OUTSIDE_ISOLATED_DIRECTORY')
        verify_runtime_identity(service_uid, private_dir, socket_dir)
        self.server = AdmissionIPCServer(gateway, socket_path,
            allowed_uids=allowed_uids, recovery_secret=recovery_secret,
            recovery_uids=recovery_uids)

    def serve(self, *, ready=None):
        verify_runtime_identity(self.service_uid, self.private_dir, self.socket_dir)
        return self.server.serve(ready=ready)

    def stop(self):
        return self.server.stop()
