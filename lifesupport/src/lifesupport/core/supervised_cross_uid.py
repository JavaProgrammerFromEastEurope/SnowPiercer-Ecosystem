"""LIFE-CORE-015: opt-in supervised, read-only cross-UID service (Linux).

This is not a production write interface or protection against root/service UID.
"""
import fcntl
import os
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path
from .service import ServiceError, _peer_uid, _send, _readline
from .cross_uid import validate_cross_uid_storage


def verified_request(path, op='health', *, expected_uid, expected_pid=None, timeout=2):
    """Verify peer credentials on the CONNECTED socket, not pathname metadata."""
    if not hasattr(socket, 'SO_PEERCRED'):
        raise ServiceError('Linux peer credentials required')
    if op not in ('health', 'snapshot', 'transition'):
        raise ServiceError('unsupported client request')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(timeout)
        conn.connect(str(path))
        import struct
        pid, uid, _gid = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != expected_uid or (expected_pid is not None and pid != expected_pid):
            raise ServiceError('IPC server identity mismatch')
        _send(conn, {'op':op})
        return _readline(conn)


def reconcile_socket(path, *, service_uid):
    """Reject symlinks, foreign objects and live sockets; unlink only stale inode."""
    path=Path(path)
    try: info=path.lstat()
    except FileNotFoundError: return
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != service_uid or stat.S_IMODE(info.st_mode)!=0o666:
        raise ServiceError('socket tampering detected')
    with socket.socket(socket.AF_UNIX) as probe:
        probe.settimeout(.2)
        try: probe.connect(str(path))
        except (ConnectionRefusedError, FileNotFoundError):
            current=path.lstat()
            if (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino):
                raise ServiceError('socket inode changed')
            path.unlink()
        except OSError as exc: raise ServiceError('socket probe failed') from exc
        else: raise ServiceError('live socket already present')


class CrossUIDSupervisor:
    """Supervise a separate process running under an already-provisioned UID.

    Does not switch privileges. Run this supervisor as the dedicated service UID.
    """
    def __init__(self, registry, db, socket_path, *, allowed_uids, cli_module="lifesupport.cross_uid_cli"):
        self.registry=Path(registry); self.db=Path(db); self.socket=Path(socket_path)
        self.allowed_uids=frozenset(allowed_uids)
        self.child=None
        self.cli_module=cli_module
        self.extra_args=()

    def run(self, *, max_restarts=None, ready_timeout=5, poll=.05):
        uid=os.geteuid()
        if not self.allowed_uids or uid in self.allowed_uids:
            raise ServiceError('dedicated service UID required')
        if not hasattr(socket,'SO_PEERCRED'): raise ServiceError('Linux required')
        d=self.socket.parent
        info=d.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=uid or stat.S_IMODE(info.st_mode)!=0o711:
            raise ServiceError('socket directory must be service-owned 0711')
        validate_cross_uid_storage(self.db,service_uid=uid,client_uid=next(iter(self.allowed_uids)))
        lock=d/'.life-cross-uid-supervisor.lock'
        fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            info=os.fstat(fd)
            if info.st_uid!=uid or stat.S_IMODE(info.st_mode)!=0o600 or not stat.S_ISREG(info.st_mode):
                raise ServiceError('unsafe supervisor lock')
            try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as exc: raise ServiceError('supervisor already active') from exc
            crashes=0
            while max_restarts is None or crashes<=max_restarts:
                reconcile_socket(self.socket,service_uid=uid)
                cmd=[sys.executable,'-m',self.cli_module,'--registry',str(self.registry),'--db',str(self.db),'--socket',str(self.socket),'--uids',','.join(map(str,sorted(self.allowed_uids)))]+list(self.extra_args)
                child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                self.child=child
                deadline=time.monotonic()+ready_timeout
                ready=False
                while time.monotonic()<deadline:
                    if child.poll() is not None: break
                    try:
                        response=verified_request(self.socket,expected_uid=uid,expected_pid=child.pid,timeout=.2)
                        ready=response.get('ok') is True or response.get('error')=='unauthorized peer UID'
                        if ready: break
                    except (OSError,ServiceError,ValueError): pass
                    time.sleep(poll)
                if not ready and child.poll() is None:
                    self.stop()
                    raise ServiceError('authorized service readiness timeout')
                while child.poll() is None: time.sleep(poll)
                crashes+=1
            return crashes
        finally:
            self.stop()
            os.close(fd)

    def stop(self):
        if self.child is not None:
            if self.child.poll() is None:
                self.child.terminate()
                try: self.child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.child.kill(); self.child.wait(timeout=2)
            self.child=None
