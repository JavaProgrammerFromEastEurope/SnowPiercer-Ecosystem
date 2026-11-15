"""RAIL-TRUST-006: fail-closed, same-UID Unix socket admission boundary.

This is an optional experimental boundary, not a privileged service or a proof
of end-to-end admission safety. Only the unified admission engine may grant PASS.
"""
from __future__ import annotations
import json
import os
import socket
import stat
import struct
from pathlib import Path
from .anchored_admission import _check_dir, _locked, _connect, _state, _read_anchor, RecoveryRequired
from .production_fencing import IndependentAnchor, inspect_fence, _inspect_fence_locked
from .trusted_admission import AdmissionError
from .unified_admission import admit, recover

class BoundaryError(AdmissionError):
    pass


def preflight(state_dir, *, provider=None):
    """Check readiness while holding the common lock; never return release PASS."""
    return inspect_fence(state_dir, provider=provider)


def _peer_uid(connection):
    if not hasattr(socket, 'SO_PEERCRED'):
        raise BoundaryError('peer credentials unavailable: fail closed')
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
    return struct.unpack('3i', raw)[1]


def _verify_socket(path, *, expected_inode=None):
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid():
        raise BoundaryError('unsafe socket path')
    if expected_inode is not None and (info.st_dev, info.st_ino) != expected_inode:
        raise BoundaryError('socket path replaced')
    return (info.st_dev, info.st_ino)


class ProductionBoundary:
    """One-request-at-a-time experimental IPC; no legacy release-gate fallback.

    Socket lifecycle is serialized by admission.lock. The caller must supply an
    authenticated independent anchor provider and must retain that provider's
    security properties outside this process. No cross-UID broker is provided.
    """
    def __init__(self, state_dir, *, provider=None):
        self.directory = _check_dir(state_dir)
        self.provider = provider if provider is not None else IndependentAnchor()
        self.socket_path = self.directory / 'release.sock'
        self.listener = None
        self.identity = None

    def start(self):
        if self.listener is not None:
            raise BoundaryError('already started')
        with _locked(self.directory):
            _inspect_fence_locked(self.directory, self.provider)
            if os.path.lexists(self.socket_path):
                raise BoundaryError('socket already exists; refusing unlink')
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                listener.bind(str(self.socket_path))
                os.chmod(self.socket_path, 0o600)
                self.identity = _verify_socket(self.socket_path)
                listener.listen(8)
                self.listener = listener
            except BaseException:
                listener.close()
                if self.identity is not None:
                    try:
                        if _verify_socket(self.socket_path) == self.identity:
                            self.socket_path.unlink()
                    except (OSError, BoundaryError):
                        pass
                raise

    def handle_one(self, *, root, baseline, attestation, trust):
        if self.listener is None:
            raise BoundaryError('not started')
        # Accept does not authorize admission. Every state-changing request must
        # re-enter the shared lifecycle lock and recheck socket and recovery fence.
        _verify_socket(self.socket_path, expected_inode=self.identity)
        connection, _ = self.listener.accept()
        with connection:
            with _locked(self.directory):
                _verify_socket(self.socket_path, expected_inode=self.identity)
                if _peer_uid(connection) != os.geteuid():
                    connection.sendall(b'{"status":"BLOCKED","reason":"peer UID"}\n')
                    return 'BLOCKED'
                connection.settimeout(3)
                request = connection.recv(256)
                if request != b'ADMIT\n':
                    connection.sendall(b'{"status":"BLOCKED","reason":"unsupported request"}\n')
                    return 'BLOCKED'
                try:
                    _inspect_fence_locked(self.directory, self.provider)
                except (AdmissionError, OSError, ValueError, TypeError) as exc:
                    result = {'status': 'BLOCKED', 'reason': type(exc).__name__}
                    connection.sendall((json.dumps(result, sort_keys=True)+'\n').encode())
                    return 'BLOCKED'
                # RAIL-TRUST-009: keep the lifecycle lock through verification,
                # external CAS, SQLite commit and response construction.
                # The private _lock_held path never acquires flock recursively.
                try:
                    result = admit(root, baseline=baseline, attestation=attestation,
                                   trust=trust, state_dir=self.directory,
                                   provider=self.provider, _lock_held=True)
                except (AdmissionError, OSError, ValueError, TypeError) as exc:
                    result = {'status': 'BLOCKED', 'reason': type(exc).__name__}
            connection.sendall((json.dumps(result, sort_keys=True)+'\n').encode())
            return result['status']

    def close(self):
        with _locked(self.directory):
            if self.listener is not None:
                self.listener.close()
                self.listener = None
            if self.identity is not None:
                try:
                    if _verify_socket(self.socket_path) == self.identity:
                        self.socket_path.unlink()
                except (OSError, BoundaryError):
                    pass
                self.identity = None
