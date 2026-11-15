"""LIFE-CORE-013: cooperative supervisor for an offline read-only IPC service.

This is not a privilege boundary against the service UID or root.
"""
from __future__ import annotations
import fcntl
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import time
from .service import ServiceError, request, _safe_dir


def _safe_stale_socket(path: Path):
    """Remove a dead socket only while holding the supervisor's exclusive lock."""
    _safe_dir(path.parent)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ServiceError('socket path tampering detected')
    probe = socket.socket(socket.AF_UNIX)
    probe.settimeout(.3)
    try:
        probe.connect(str(path))
    except (ConnectionRefusedError, FileNotFoundError):
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ServiceError('socket changed during recovery')
        path.unlink()
    except OSError as exc:
        raise ServiceError(f'cannot validate stale socket: {exc}') from exc
    else:
        raise ServiceError('another live service owns socket')
    finally:
        probe.close()


def validate_production_paths(db_path, socket_path, *, service_uid, client_uid):
    """Fail closed unless OS ownership separates service files from client UID."""
    if service_uid == client_uid or os.geteuid() != service_uid:
        raise ServiceError('production requires dedicated service UID distinct from client UID')
    sock = Path(socket_path)
    _safe_dir(sock.parent)
    db = Path(db_path)
    if db.is_symlink() or db.parent.resolve() != sock.parent.resolve():
        raise ServiceError('production database must reside in private service directory')
    if db.exists():
        info = db.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != service_uid or stat.S_IMODE(info.st_mode) != 0o600:
            raise ServiceError('production database ownership or mode invalid')
    for extra in (str(db)+'-wal', str(db)+'-shm'):
        p = Path(extra)
        if p.exists() or p.is_symlink():
            info=p.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != service_uid or stat.S_IMODE(info.st_mode)&0o077:
                raise ServiceError('SQLite sidecar permissions invalid')
    return True


class ServiceSupervisor:
    def __init__(self, registry, db, socket_path, *, production=False, client_uid=None):
        self.registry=Path(registry); self.db=Path(db); self.socket=Path(socket_path)
        self.production=production; self.client_uid=client_uid
        self.child=None

    def run(self, *, max_restarts=None, ready_timeout=5, poll=.05):
        _safe_dir(self.socket.parent)
        if self.production:
            if self.client_uid is None: raise ServiceError('client UID required')
            validate_production_paths(self.db,self.socket,service_uid=os.geteuid(),client_uid=self.client_uid)
        lock_path=self.socket.parent/'.life-supervisor.lock'
        fd=os.open(lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            if os.fstat(fd).st_uid != os.geteuid() or stat.S_IMODE(os.fstat(fd).st_mode)!=0o600:
                raise ServiceError('supervisor lock permissions invalid')
            try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as exc: raise ServiceError('supervisor already running') from exc
            restarts=0
            while max_restarts is None or restarts <= max_restarts:
                _safe_stale_socket(self.socket)
                cmd=[sys.executable,'-m','lifesupport.service_cli','--registry',str(self.registry),'--db',str(self.db),'--socket',str(self.socket)]
                self.child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                deadline=time.monotonic()+ready_timeout
                while time.monotonic()<deadline and self.child.poll() is None:
                    try:
                        if request(self.socket,timeout=.2).get('ok'): break
                    except (OSError,ServiceError,ValueError): pass
                    time.sleep(poll)
                else:
                    if self.child.poll() is not None:
                        restarts += 1
                        continue
                    self.stop()
                    raise ServiceError('child readiness timeout')
                while self.child.poll() is None:
                    time.sleep(poll)
                restarts+=1
            return restarts
        finally:
            self.stop()
            os.close(fd)

    def stop(self):
        if self.child is not None:
            if self.child.poll() is None:
                self.child.terminate()
                try:self.child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.child.kill(); self.child.wait(timeout=2)
            self.child=None
