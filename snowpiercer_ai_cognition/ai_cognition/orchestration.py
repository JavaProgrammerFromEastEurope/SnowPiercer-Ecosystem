"""AI-CORE-011: fail-closed production orchestration (Linux).

Supervisor does not reconcile audit checkpoints. A fresh service process must
construct a fresh gateway and verify anchors before publishing its socket.
"""
import os
import signal
import socket
import stat
import subprocess
import time
from pathlib import Path
from .service_identity import IsolationError
from .isolation import ipc_request


def production_admission(gateway, *, production=False):
    """Library compatibility: production must use IPC, never direct admission."""
    if production:
        raise IsolationError('PRODUCTION_IPC_REQUIRED')
    return gateway


def verified_socket(path, *, owner_uid):
    info = Path(path).lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != owner_uid or info.st_nlink != 1:
        raise IsolationError('SOCKET_IDENTITY_INVALID')
    return (info.st_dev, info.st_ino)


class AdmissionSupervisor:
    """Launch a fresh process on every attempt; no automatic recovery authorization.

    `command` must start a service which checks gateway.verify() before binding.
    The OS service account is selected using subprocess.Popen(user=...) on Linux.
    Supervisor is trusted and must own the process lifecycle.
    """
    def __init__(self, command, socket_path, *, service_uid, max_restarts=2,
                 startup_timeout=5, poll_interval=.05, env=None, service_gid=None):
        if os.name != 'posix' or not hasattr(socket, 'SO_PEERCRED'):
            raise RuntimeError('LINUX_REQUIRED')
        if not isinstance(service_uid, int) or service_uid <= 0:
            raise IsolationError('DEDICATED_UID_REQUIRED')
        if not isinstance(command, (list, tuple)) or not command or not all(isinstance(x,str) for x in command):
            raise ValueError('command')
        if not isinstance(max_restarts,int) or max_restarts < 0: raise ValueError('max_restarts')
        self.command=list(command); self.socket_path=Path(socket_path)
        self.service_uid=service_uid; self.max_restarts=max_restarts
        self.startup_timeout=startup_timeout; self.poll_interval=poll_interval
        self.env=env; self.service_gid=service_gid; self.process=None; self.restarts=0; self.ready=False

    def _start(self):
        self.ready=False
        directory=self.socket_path.parent.lstat()
        if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != self.service_uid or stat.S_IMODE(directory.st_mode) != 0o710:
            raise IsolationError('UNSAFE_SOCKET_DIRECTORY')
        if self.socket_path.is_symlink(): raise IsolationError('SOCKET_REPLACEMENT_DETECTED')
        # The service itself must validate/reclaim stale sockets in its private directory.
        self.process=subprocess.Popen(self.command, user=self.service_uid,
                                      **({"group": self.service_gid} if self.service_gid is not None else {}),
                                      env=self.env, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      close_fds=True, start_new_session=True)
        deadline=time.monotonic()+self.startup_timeout
        while time.monotonic()<deadline:
            if self.process.poll() is not None:
                raise IsolationError('SERVICE_START_FAILED')
            try:
                identity=verified_socket(self.socket_path,owner_uid=self.service_uid)
                reply=ipc_request(self.socket_path,{'op':'verify'},timeout=.3)
                if reply.get('ok') is not True: raise IsolationError('RECOVERY_FENCED')
                if verified_socket(self.socket_path,owner_uid=self.service_uid)!=identity:
                    raise IsolationError('SOCKET_REPLACEMENT_DETECTED')
                self.ready=True
                return
            except (FileNotFoundError, ConnectionRefusedError, ConnectionResetError, BrokenPipeError, TimeoutError, socket.timeout):
                time.sleep(self.poll_interval)
        raise IsolationError('SERVICE_NOT_READY')

    def run(self, *, stop_event):
        """Blocking supervision. stop_event is a threading.Event-like object."""
        try:
            while not stop_event.is_set():
                try:
                    self._start()
                except BaseException:
                    self._terminate()
                    raise
                while not stop_event.wait(self.poll_interval):
                    if self.process.poll() is not None: break
                if stop_event.is_set(): break
                if self.restarts >= self.max_restarts:
                    raise IsolationError('RESTART_BUDGET_EXHAUSTED')
                self.restarts += 1
                # Fresh child must validate DB/checkpoint; never grant recovery.
            return self.restarts
        finally:
            self._terminate()

    def _terminate(self):
        child=self.process
        if child is None: return
        if child.poll() is None:
            child.terminate()
            try: child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
        else:
            child.wait()
        self.process=None
