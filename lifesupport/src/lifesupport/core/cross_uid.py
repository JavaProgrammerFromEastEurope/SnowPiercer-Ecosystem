"""LIFE-CORE-014: Linux peer-credential authorization for read-only IPC.

Production writes are intentionally unavailable. OS DAC, not this module,
protects the database from a distinct unprivileged client UID.
"""
import os
import socket
import stat
from pathlib import Path
from .service import ServiceError, _peer_uid, _send, _readline


def authorize_peer(conn, *, allowed_uids):
    """Reject unknown UID before reading a request (Linux SO_PEERCRED)."""
    if not hasattr(socket, 'SO_PEERCRED'):
        raise ServiceError('Linux peer credentials required')
    if not isinstance(allowed_uids, (set, frozenset)) or not allowed_uids or any(type(x) is not int or x < 0 for x in allowed_uids):
        raise ServiceError('invalid UID allowlist')
    uid = _peer_uid(conn)
    if uid not in allowed_uids:
        raise ServiceError('unauthorized peer UID')
    return uid


def validate_cross_uid_storage(db_path, *, service_uid, client_uid):
    """Validate DAC boundary for DB and its WAL/SHM sidecars.

    Caller must provision a private owner-only storage directory separately
    from any group-accessible socket directory.
    """
    if service_uid == client_uid or service_uid < 0 or client_uid < 0:
        raise ServiceError('dedicated service UID required')
    db = Path(db_path)
    parent = db.parent
    ps = parent.lstat()
    if not stat.S_ISDIR(ps.st_mode) or ps.st_uid != service_uid or stat.S_IMODE(ps.st_mode) != 0o700:
        raise ServiceError('database directory must be service-owned 0700')
    for p in (db, Path(str(db)+'-wal'), Path(str(db)+'-shm')):
        try: info=p.lstat()
        except FileNotFoundError: continue
        if not stat.S_ISREG(info.st_mode) or info.st_uid != service_uid or stat.S_IMODE(info.st_mode) != 0o600:
            raise ServiceError('database file or sidecar must be service-owned 0600')
    return True


def serve_authorized_connection(conn, lifecycle, *, allowed_uids):
    """Single connection handler; no remote state-changing operation exists."""
    authorize_peer(conn, allowed_uids=allowed_uids)
    req=_readline(conn)
    if not isinstance(req,dict) or set(req) != {'op'}:
        raise ServiceError('invalid IPC request')
    if req['op']=='health':
        lifecycle.verify_integrity()
        lifecycle._replay()
        return {'ok':True,'status':'ready'}
    if req['op']=='snapshot':
        lifecycle.verify_integrity()
        return {'ok':True,'states':lifecycle._replay().snapshot()}
    raise ServiceError('production writes are disabled')

class AuthorizedLifecycleService:
    """Opt-in cross-UID read-only service with kernel-credential authorization.

    Socket directory is service-owned 0711 and socket 0666 to permit connection;
    SO_PEERCRED decides authorization. DB must live in separate private 0700 dir.
    """
    def __init__(self, registry_path, db_path, socket_path, *, allowed_uids):
        self.registry_path=Path(registry_path)
        self.db_path=Path(db_path)
        self.socket_path=Path(socket_path)
        self.allowed_uids=frozenset(allowed_uids)
        if not self.allowed_uids or os.geteuid() in self.allowed_uids:
            raise ServiceError('cross-UID allowlist must exclude service UID')

    def serve(self, *, stop_event=None):
        from .registry import Registry
        from .hardening import HardenedLifecycle
        import threading
        if not hasattr(socket,'SO_PEERCRED'):
            raise ServiceError('Linux SO_PEERCRED required')
        d=self.socket_path.parent
        ds=d.lstat()
        if not stat.S_ISDIR(ds.st_mode) or ds.st_uid!=os.geteuid() or stat.S_IMODE(ds.st_mode)!=0o711:
            raise ServiceError('socket directory must be service-owned 0711')
        validate_cross_uid_storage(self.db_path,service_uid=os.geteuid(),client_uid=next(iter(self.allowed_uids)))
        if self.socket_path.exists() or self.socket_path.is_symlink():
            raise ServiceError('socket occupied; supervisor must reconcile')
        if not self.db_path.exists():
            fd=os.open(self.db_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            os.close(fd)
        registry=Registry.load(self.registry_path)
        lifecycle=HardenedLifecycle(registry,self.db_path)
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            listener.bind(str(self.socket_path))
            os.chmod(self.socket_path,0o666)
            listener.listen(32)
            listener.settimeout(.2)
            while stop_event is None or not stop_event.is_set():
                try: conn,_=listener.accept()
                except socket.timeout: continue
                with conn:
                    conn.settimeout(2)
                    try: result=serve_authorized_connection(conn,lifecycle,allowed_uids=self.allowed_uids)
                    except Exception as exc: result={'ok':False,'error':str(exc)}
                    try: _send(conn,result)
                    except OSError: pass
        finally:
            listener.close()
            lifecycle.close()
            try:
                if self.socket_path.is_socket(): self.socket_path.unlink()
            except OSError: pass


def cross_uid_request(socket_path, op='health'):
    """Client call: do not assume socket metadata authenticates the server."""
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
        conn.settimeout(2)
        conn.connect(str(socket_path))
        _send(conn,{'op':op})
        return _readline(conn)
