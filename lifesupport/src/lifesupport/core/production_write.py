"""LIFE-CORE-016: opt-in offline write IPC under dedicated Linux UID.

No hardware actuation. Security boundary relies on kernel DAC and credential checks.
"""
import os
import socket
import stat
import threading
from pathlib import Path
from .service import ServiceError, _send, _readline
from .cross_uid import authorize_peer, validate_cross_uid_storage
from .registry import Registry
from .hardening import HardenedLifecycle

FIELDS = frozenset(('op','component_id','next_state','event_id','reason'))


def validate_identity(*, allowed_uids):
    uid=os.geteuid()
    if uid == 0 or not allowed_uids or uid in allowed_uids or any(type(x) is not int or x <= 0 for x in allowed_uids):
        raise ServiceError('dedicated unprivileged service UID and distinct client UID required')
    if not hasattr(socket,'SO_PEERCRED'):
        raise ServiceError('Linux peer credentials required')
    return uid


def process_write(conn, lifecycle, *, allowed_uids):
    uid=authorize_peer(conn,allowed_uids=allowed_uids)
    req=_readline(conn)
    if not isinstance(req,dict) or not isinstance(req.get('op'),str):
        raise ServiceError('invalid IPC request')
    if req['op'] in ('health','snapshot'):
        if set(req)!= {'op'}: raise ServiceError('unexpected fields')
        lifecycle.verify_integrity()
        state=lifecycle._replay()
        return {'ok':True,'status':'ready'} if req['op']=='health' else {'ok':True,'states':state.snapshot()}
    if req['op']!='transition' or set(req)!=FIELDS:
        raise ServiceError('unsupported operation or fields')
    if any(type(req[k]) is not str or not req[k] or len(req[k])>256 for k in FIELDS-{'op'}):
        raise ServiceError('invalid transition arguments')
    # Server, not client, selects the audit actor and owns the fence token.
    lifecycle.verify_integrity()
    token=lifecycle.acquire('ipc-service',ttl_ns=10_000_000_000)
    try:
        event=lifecycle.transition(req['component_id'],req['next_state'],event_id=req['event_id'],reason=req['reason'],actor=f'uid:{uid}',token=token)
    finally:
        lifecycle.release(token)
    return {'ok':True,'sequence':event.sequence,'event_id':event.event_id}


class ProductionWriteService:
    """Opt-in IPC service; caller provisions private 0700 DB dir and 0711 socket dir."""
    def __init__(self, registry_path, db_path, socket_path, *, allowed_uids):
        self.registry_path=Path(registry_path)
        self.db_path=Path(db_path)
        self.socket_path=Path(socket_path)
        self.allowed_uids=frozenset(allowed_uids)
        self._stop=threading.Event()

    def serve(self):
        uid=validate_identity(allowed_uids=self.allowed_uids)
        d=self.socket_path.parent
        info=d.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=uid or stat.S_IMODE(info.st_mode)!=0o711:
            raise ServiceError('unsafe socket directory')
        validate_cross_uid_storage(self.db_path,service_uid=uid,client_uid=next(iter(self.allowed_uids)))
        if self.socket_path.exists() or self.socket_path.is_symlink():
            raise ServiceError('occupied socket')
        if not self.db_path.exists():
            fd=os.open(self.db_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            os.close(fd)
        lifecycle=HardenedLifecycle(Registry.load(self.registry_path),self.db_path)
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        bound_inode=None
        try:
            # Require existing v2 protection. Migration is explicit, offline.
            if lifecycle.verify_integrity().get('version')!=2:
                raise ServiceError('v2 protected database required; provision offline')
            self.preflight(lifecycle)
            listener.bind(str(self.socket_path))
            bound_inode=os.lstat(self.socket_path)
            os.chmod(self.socket_path,0o666)
            listener.listen(32)
            listener.settimeout(.2)
            while not self._stop.is_set():
                try: conn,_=listener.accept()
                except socket.timeout: continue
                with conn:
                    conn.settimeout(2)
                    try: response=self.handle(conn,lifecycle)
                    except Exception as exc: response={'ok':False,'error':str(exc)}
                    try: _send(conn,response)
                    except OSError: pass
        finally:
            listener.close()
            lifecycle.close()
            if bound_inode is not None:
                try:
                    now=os.lstat(self.socket_path)
                    if stat.S_ISSOCK(now.st_mode) and (now.st_dev,now.st_ino)==(bound_inode.st_dev,bound_inode.st_ino):
                        self.socket_path.unlink()
                except FileNotFoundError: pass

    def preflight(self,lifecycle):
        """Overridable startup admission; legacy behavior unchanged."""
        return None

    def handle(self,conn,lifecycle):
        return process_write(conn,lifecycle,allowed_uids=self.allowed_uids)

    def stop(self): self._stop.set()
