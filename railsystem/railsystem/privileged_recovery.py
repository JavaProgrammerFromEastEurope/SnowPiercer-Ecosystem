"""RAIL-TRUST-011: OS-gated cross-UID recovery service endpoint.

Run under a dedicated trusted service UID; its private state directory MUST be
unreachable by client UIDs. The IPC directory and transport GID MUST be
provisioned by the operating-system service manager. This library does not
start a privileged daemon, grant privileges, or implement an independent anchor.
"""
from __future__ import annotations
import json
import os
import socket
import stat
from pathlib import Path
from .anchored_admission import _check_dir, _locked
from .production_fencing import IndependentAnchor
from .durable_permits import IndependentPermitLedger, PermitLedgerUnavailable
from .recovery_broker import authorize_peer, BrokerDenied
from .trusted_admission import AdmissionError
from .unified_admission import recover, _tuple


class PrivilegedBrokerDenied(BrokerDenied):
    pass


def _ipc_dir(directory, gid):
    path = Path(directory)
    info = path.lstat()  # never resolve a symlink
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_gid != gid or stat.S_IMODE(info.st_mode) != 0o750):
        raise PrivilegedBrokerDenied('IPC directory must be service-owned 0750 with operator-provisioned GID')
    return path


class PrivilegedRecoveryBroker:
    """One-request broker with kernel UID authorization and group-gated transport.

    `state_dir`: 0700, service-owned, not accessible by clients.
    `ipc_dir`: 0750, service-owned, dedicated shared transport group.
    The socket is 0660, with group transport_gid; an explicit UID allowlist
    additionally constrains authenticated peers. Recovery permit is delivered
    out-of-band to the service and NEVER accepted as IPC client input.
    """
    def __init__(self, state_dir, ipc_dir, *, transport_gid, allowed_uids,
                 provider=None, permit_store=None):
        if type(transport_gid) is not int or transport_gid < 0:
            raise PrivilegedBrokerDenied('invalid transport GID')
        if (not isinstance(allowed_uids, frozenset) or not allowed_uids
                or any(type(uid) is not int or uid < 0 or uid == os.geteuid() for uid in allowed_uids)):
            raise PrivilegedBrokerDenied('explicit non-service client UIDs required')
        self.state_dir = _check_dir(state_dir)
        self.ipc_dir = _ipc_dir(ipc_dir, transport_gid)
        self.transport_gid = transport_gid
        self.allowed_uids = allowed_uids
        self.provider = provider if provider is not None else IndependentAnchor()
        self.permit_store = permit_store if permit_store is not None else IndependentPermitLedger()
        self.path = self.ipc_dir / 'recovery-v011.sock'
        self.listener = None
        self.identity = None

    def _verify_path(self):
        info = self.path.lstat()
        if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_gid != self.transport_gid
                or stat.S_IMODE(info.st_mode) != 0o660
                or (info.st_dev, info.st_ino) != self.identity):
            raise PrivilegedBrokerDenied('recovery socket substituted')

    def _remove_owned(self):
        try:
            self._verify_path()
        except (OSError, PrivilegedBrokerDenied):
            return
        self.path.unlink()

    def start(self):
        if self.listener is not None:
            raise PrivilegedBrokerDenied('already running')
        with _locked(self.state_dir):
            _ipc_dir(self.ipc_dir, self.transport_gid)
            _tuple(self.provider.read())  # anchor response must be valid
            if self.permit_store.check_ready() is not True:
                raise PermitLedgerUnavailable('permit ledger did not attest readiness')
            if os.path.lexists(self.path):
                raise PrivilegedBrokerDenied('recovery socket occupied; never unlink unknown path')
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(str(self.path))
                os.chown(self.path, os.geteuid(), self.transport_gid)
                os.chmod(self.path, 0o660)
                info = self.path.lstat()
                self.identity = (info.st_dev, info.st_ino)
                self._verify_path()
                sock.listen(8)
                self.listener = sock
            except BaseException:
                sock.close()
                if self.identity is not None:
                    self._remove_owned()
                self.identity = None
                raise

    def handle_one(self, *, permit, recovery_public_key):
        if self.listener is None:
            raise PrivilegedBrokerDenied('not started')
        self._verify_path()
        connection, _ = self.listener.accept()
        with connection:
            connection.settimeout(3)
            try:
                # No state lock is held across socket recv; timeout bounds an
                # unresponsive client. All state changes acquire it afterward.
                authorize_peer(connection, self.allowed_uids)
                if connection.recv(128) != b'RECONCILE\n':
                    raise PrivilegedBrokerDenied('unsupported IPC verb')
                with _locked(self.state_dir):
                    _ipc_dir(self.ipc_dir, self.transport_gid)
                    self._verify_path()
                    if self.permit_store.check_ready() is not True:
                        raise PermitLedgerUnavailable('permit ledger unavailable during recovery')
                    result = recover(self.state_dir, provider=self.provider,
                                     permit=permit, recovery_public_key=recovery_public_key,
                                     permit_store=self.permit_store, _lock_held=True)
            except (AdmissionError, OSError, ValueError, TypeError, TimeoutError):
                result = {'status': 'BLOCKED'}
            connection.sendall((json.dumps(result, sort_keys=True)+'\n').encode('utf-8'))
            return result['status']

    def close(self):
        with _locked(self.state_dir):
            if self.listener is not None:
                self.listener.close()
                self.listener = None
            if self.identity is not None:
                self._remove_owned()
                self.identity = None
