"""RAIL-TRUST-010: fail-closed recovery broker boundary.

A trusted service manager must provision the socket and independently trusted
anchor. This module never grants cross-UID recovery merely because a permit is
signed: the peer UID must be explicitly authorized by the operator.
"""
from __future__ import annotations
import json
import os
import socket
import stat
import struct
from pathlib import Path
from .anchored_admission import _check_dir, _locked
from .production_fencing import IndependentAnchor
from .unified_admission import recover
from .trusted_admission import AdmissionError

class BrokerDenied(AdmissionError):
    pass


def peer_uid(connection):
    if not hasattr(socket, 'SO_PEERCRED'):
        raise BrokerDenied('peer credential verification unavailable')
    data = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
    return struct.unpack('3i', data)[1]


def authorize_peer(connection, allowed_uids):
    if not isinstance(allowed_uids, frozenset) or not allowed_uids or any(type(x) is not int or x < 0 for x in allowed_uids):
        raise BrokerDenied('invalid explicit UID allowlist')
    uid = peer_uid(connection)
    if uid not in allowed_uids:
        raise BrokerDenied('unauthorized recovery peer')
    return uid


class RecoveryBroker:
    """One-request broker. Caller supplies trusted permit from separate channel.

    No arbitrary permit material is accepted over IPC. The connection can only
    trigger a pre-authorized reconcile action, never select a target sequence.
    """
    def __init__(self, state_dir, *, provider=None, allowed_uids=frozenset()):
        self.directory = _check_dir(state_dir)
        self.provider = provider if provider is not None else IndependentAnchor()
        self.allowed_uids = allowed_uids
        self.path = self.directory / 'recovery.sock'
        self.listener = None
        self.identity = None

    def start(self):
        if self.listener is not None:
            raise BrokerDenied('already started')
        with _locked(self.directory):
            if not self.allowed_uids or not isinstance(self.allowed_uids, frozenset):
                raise BrokerDenied('no authorized recovery identities')
            self.provider.read()  # fail closed without an independent anchor
            if os.path.lexists(self.path):
                raise BrokerDenied('recovery socket path occupied')
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(str(self.path))
                os.chmod(self.path, 0o600)
                info = self.path.lstat()
                if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid():
                    raise BrokerDenied('unsafe recovery socket')
                self.identity = (info.st_dev, info.st_ino)
                sock.listen(2)
                self.listener = sock
            except BaseException:
                sock.close()
                if self.identity is not None:
                    self._unlink_owned()
                raise

    def _verify_path(self):
        info = self.path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid() or (info.st_dev, info.st_ino) != self.identity:
            raise BrokerDenied('recovery socket identity changed')

    def _unlink_owned(self):
        try:
            self._verify_path()
            self.path.unlink()
        except (OSError, BrokerDenied):
            pass

    def handle_one(self, *, permit, recovery_public_key):
        if self.listener is None:
            raise BrokerDenied('broker not started')
        self._verify_path()
        connection, _ = self.listener.accept()
        with connection:
            connection.settimeout(3)
            try:
                self._verify_path()
                authorize_peer(connection, self.allowed_uids)
                if connection.recv(64) != b'RECONCILE\n':
                    raise BrokerDenied('unsupported recovery request')
                result = recover(self.directory, provider=self.provider, permit=permit,
                                 recovery_public_key=recovery_public_key)
            except (AdmissionError, OSError, ValueError, TypeError) as exc:
                result = {'status': 'BLOCKED', 'reason': type(exc).__name__}
            connection.sendall((json.dumps(result, sort_keys=True) + '\n').encode())
            return result['status']

    def close(self):
        with _locked(self.directory):
            if self.listener is not None:
                self.listener.close()
                self.listener = None
            if self.identity is not None:
                self._unlink_owned()
                self.identity = None
