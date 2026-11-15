"""LIFE-CORE-012: Unix IPC owner-only offline lifecycle service.

Not a security boundary against same-UID processes or privileged DB access.
"""
from __future__ import annotations
import json, os, socket, stat, struct, threading, time
from pathlib import Path
from .registry import Registry
from .hardening import HardenedLifecycle

class ServiceError(RuntimeError): pass
MAX_FRAME=65536

def _safe_dir(path):
    p=Path(path)
    if p.is_symlink() or not p.is_dir(): raise ServiceError('invalid socket directory')
    s=p.stat()
    if s.st_uid != os.geteuid() or stat.S_IMODE(s.st_mode)!=0o700: raise ServiceError('socket directory must be owner-owned 0700')

def _readline(sock):
    data=bytearray()
    while len(data)<MAX_FRAME:
        ch=sock.recv(1)
        if not ch: break
        if ch==b'\n': break
        data.extend(ch)
    else: raise ServiceError('frame too large')
    if not data: raise ServiceError('empty request')
    return json.loads(data)

def _send(sock, obj):
    payload=json.dumps(obj,sort_keys=True).encode()+b'\n'
    if len(payload)>MAX_FRAME: raise ServiceError('response too large')
    sock.sendall(payload)

def _peer_uid(sock):
    if not hasattr(socket,'SO_PEERCRED'): raise ServiceError('SO_PEERCRED unavailable')
    return struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]

class LifecycleService:
    def __init__(self, registry_path, db_path, socket_path):
        self.registry_path=Path(registry_path); self.db_path=Path(db_path); self.socket_path=Path(socket_path)
        self._stop=threading.Event()
    def serve(self):
        _safe_dir(self.socket_path.parent)
        if self.socket_path.exists() or self.socket_path.is_symlink(): raise ServiceError('socket path already occupied')
        # DB is exclusively owned by the service's UID; legacy APIs cannot be
        # blocked for a client running under that same UID.
        if self.db_path.exists():
            s=self.db_path.stat()
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid() or stat.S_IMODE(s.st_mode)&0o077:
                raise ServiceError('database owner/mode invalid')
        else:
            fd=os.open(self.db_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.close(fd)
        os.chmod(self.db_path,0o600)
        registry=Registry.load(self.registry_path)
        lifecycle=HardenedLifecycle(registry,self.db_path)
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            listener.bind(str(self.socket_path)); os.chmod(self.socket_path,0o600)
            listener.listen(32); listener.settimeout(.2)
            while not self._stop.is_set():
                try: conn,_=listener.accept()
                except socket.timeout: continue
                with conn:
                    conn.settimeout(3)
                    try:
                        if _peer_uid(conn)!=os.geteuid(): raise ServiceError('peer UID denied')
                        req=_readline(conn)
                        if not isinstance(req,dict) or set(req)-{'op'}: raise ServiceError('invalid request')
                        if req.get('op')=='health':
                            lifecycle.verify_integrity(); lifecycle.recover(token=None) if False else lifecycle._replay()
                            result={'ok':True,'status':'ready','pid':os.getpid()}
                        elif req.get('op')=='snapshot':
                            lifecycle.verify_integrity(); recovered=lifecycle._replay()
                            result={'ok':True,'states':recovered.snapshot()}
                        else: raise ServiceError('unsupported operation; physical writes disabled')
                    except Exception as exc: result={'ok':False,'error':str(exc)}
                    try:_send(conn,result)
                    except (BrokenPipeError,ConnectionResetError,OSError): pass
        finally:
            listener.close(); lifecycle.close()
            try:
                if self.socket_path.is_socket(): self.socket_path.unlink()
            except OSError: pass
    def stop(self): self._stop.set()

def request(socket_path, op='health', timeout=2):
    path=Path(socket_path)
    _safe_dir(path.parent)
    if not path.is_socket() or path.is_symlink(): raise ServiceError('not a trusted socket')
    s=path.stat()
    if s.st_uid!=os.geteuid() or stat.S_IMODE(s.st_mode)!=0o600: raise ServiceError('socket owner/mode invalid')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout); sock.connect(str(path)); _send(sock,{'op':op}); return _readline(sock)
