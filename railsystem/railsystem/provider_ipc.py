"""RAIL-TRUST-012: authenticated, bounded Unix RPC to independently owned providers.

Kernel peer UID authenticates the endpoint *process*, not the correctness,
non-rollbackability or durability of its storage. No provider implementation
is shipped for production. A failed/ambiguous RPC is always fail closed.
"""
from __future__ import annotations
import json
import os
import socket
import stat
import struct
from pathlib import Path
from .production_fencing import IndependentAnchor, IndependentAnchorUnavailable
from .durable_permits import IndependentPermitLedger, PermitLedgerUnavailable

MAX_REPLY = 4096


class RemoteProviderUnavailable(IndependentAnchorUnavailable, PermitLedgerUnavailable):
    pass


class AuthenticatedUnixRPC:
    def __init__(self, socket_path, *, expected_uid: int, expected_gid: int, timeout=2.0):
        if (not isinstance(expected_uid, int) or isinstance(expected_uid, bool)
                or expected_uid < 1 or type(expected_gid) is not int or expected_gid < 0
                or not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
                or not 0 < timeout <= 10):
            raise RemoteProviderUnavailable('invalid provider peer identity or timeout')
        self.path = Path(socket_path)
        if not self.path.is_absolute() or self.path.name in ('', '.', '..'):
            raise RemoteProviderUnavailable('absolute provider socket required')
        self.uid = expected_uid
        self.gid = expected_gid
        self.timeout = timeout

    def _path_identity(self):
        parent = self.path.parent
        p = parent.lstat()
        s = self.path.lstat()
        if (not stat.S_ISDIR(p.st_mode) or stat.S_IMODE(p.st_mode) != 0o750
                or p.st_uid != self.uid or p.st_gid != self.gid
                or not stat.S_ISSOCK(s.st_mode) or s.st_uid != self.uid
                or s.st_gid != self.gid or stat.S_IMODE(s.st_mode) != 0o660):
            raise RemoteProviderUnavailable('provider IPC path ownership or mode mismatch')
        return s.st_dev, s.st_ino

    def call(self, kind, operation, **fields):
        if not hasattr(socket, 'SO_PEERCRED'):
            raise RemoteProviderUnavailable('kernel peer credentials unavailable')
        try:
            identity = self._path_identity()
            payload = {'domain': 'snowpiercer.railsystem.provider.v1', 'kind': kind,
                       'operation': operation, **fields}
            encoded = json.dumps(payload, sort_keys=True, allow_nan=False).encode('utf8') + b'\n'
            if len(encoded) > MAX_REPLY:
                raise RemoteProviderUnavailable('request too large')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.settimeout(self.timeout)
                conn.connect(str(self.path))
                peer = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET,
                                   socket.SO_PEERCRED, struct.calcsize('3i')))
                if peer[1] != self.uid or peer[2] != self.gid:
                    raise RemoteProviderUnavailable('provider peer UID/GID mismatch')
                if self._path_identity() != identity:
                    raise RemoteProviderUnavailable('provider socket changed during connect')
                conn.sendall(encoded)
                buf = bytearray()
                while len(buf) <= MAX_REPLY:
                    block = conn.recv(min(1024, MAX_REPLY + 1 - len(buf)))
                    if not block:
                        break
                    buf.extend(block)
                    if b'\n' in block:
                        break
            if not buf.endswith(b'\n') or len(buf) > MAX_REPLY or b'\n' in buf[:-1]:
                raise RemoteProviderUnavailable('incomplete or oversized provider reply')
            answer = json.loads(buf)
            if (type(answer) is not dict or answer.get('domain') != payload['domain']
                    or answer.get('kind') != kind or answer.get('operation') != operation):
                raise RemoteProviderUnavailable('invalid provider response envelope')
            if answer.get('status') != 'OK':
                raise RemoteProviderUnavailable('provider rejected request')
            return answer
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RemoteProviderUnavailable('provider unavailable or unauthenticated') from exc


class UnixAnchorClient(IndependentAnchor):
    def __init__(self, socket_path, *, expected_uid, expected_gid, timeout=2.0):
        self.rpc = AuthenticatedUnixRPC(socket_path, expected_uid=expected_uid,
                                        expected_gid=expected_gid, timeout=timeout)

    def read(self):
        response = self.rpc.call('anchor', 'read')
        seq, nonce = response.get('sequence'), response.get('nonce')
        if type(seq) is not int or seq < 0 or type(nonce) is not str or len(nonce) > 128:
            raise RemoteProviderUnavailable('invalid anchor read')
        return seq, nonce

    def advance(self, expected, next_value):
        for value in (expected, next_value):
            if (not isinstance(value, (list, tuple)) or len(value) != 2
                    or type(value[0]) is not int or value[0] < 0
                    or type(value[1]) is not str or len(value[1]) > 128):
                raise RemoteProviderUnavailable('invalid CAS argument')
        if next_value[0] <= expected[0]:
            raise RemoteProviderUnavailable('non-monotonic CAS requested')
        response = self.rpc.call('anchor', 'advance', expected=list(expected), next=list(next_value))
        if type(response.get('advanced')) is not bool:
            raise RemoteProviderUnavailable('invalid CAS acknowledgement')
        return response['advanced']


class UnixPermitLedgerClient(IndependentPermitLedger):
    def __init__(self, socket_path, *, expected_uid, expected_gid, timeout=2.0):
        self.rpc = AuthenticatedUnixRPC(socket_path, expected_uid=expected_uid,
                                        expected_gid=expected_gid, timeout=timeout)

    def check_ready(self):
        response = self.rpc.call('permit', 'ready')
        if response.get('ready') is not True:
            raise RemoteProviderUnavailable('permit ledger not ready')
        return True

    def consume_once(self, digest, *, sequence, action):
        if (type(digest) is not str or len(digest) != 64
                or any(c not in '0123456789abcdef' for c in digest)
                or type(sequence) is not int or sequence < 1 or action != 'reconcile'):
            raise RemoteProviderUnavailable('invalid permit consumption request')
        response = self.rpc.call('permit', 'consume', digest=digest,
                                 sequence=sequence, action=action)
        if type(response.get('consumed')) is not bool:
            raise RemoteProviderUnavailable('ambiguous permit consumption acknowledgement')
        return response['consumed']
