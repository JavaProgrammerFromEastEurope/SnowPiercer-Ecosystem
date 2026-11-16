"""ISLAND-GEO-009 experimental fail-closed production IPC facade.

No assertion of OS isolation: deployment must provision separate UIDs and directories.
The legacy AnchoredAdmission API remains available for offline/library compatibility,
not a production security boundary. This module cannot fence arbitrary legacy callers.
"""
import json
import os
import socket
import stat
import struct
from pathlib import Path
from .anchored_admission import AnchoredAdmission, WitnessClient, AdmissionDenied, _receive, _send

MAX_PAYLOAD = 4096

def secure_directory(path, owner_uid=None):
    p = Path(path)
    s = p.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_mode & 0o022:
        raise AdmissionDenied('unsafe directory permissions or type')
    if owner_uid is not None and s.st_uid != owner_uid:
        raise AdmissionDenied('directory owner mismatch')
    return p

def secure_regular(path, owner_uid=None):
    p = Path(path)
    s = p.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_mode & 0o022:
        raise AdmissionDenied('unsafe file permissions, link or type')
    if owner_uid is not None and s.st_uid != owner_uid:
        raise AdmissionDenied('file owner mismatch')
    return p

def peer_uid(sock):
    if not hasattr(socket, 'SO_PEERCRED'):
        raise AdmissionDenied('peer credential mechanism unavailable')
    return struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]

class ProductionAdmissionServer:
    """Bounded Unix socket service. Admission is mandatory on this endpoint only."""
    def __init__(self, socket_path, local_db, witness_socket, client_uids, witness_uid=None):
        self.socket_path = Path(socket_path)
        self.local_db = Path(local_db)
        self.witness_socket = Path(witness_socket)
        self.client_uids = frozenset(client_uids)
        self.witness_uid = witness_uid
        self.witness_client_factory = WitnessClient
        if not self.client_uids or any(type(x) is not int or x < 0 for x in self.client_uids):
            raise AdmissionDenied('invalid client UID allowlist')
    def _preflight(self):
        secure_directory(self.socket_path.parent)
        secure_directory(self.local_db.parent)
        secure_directory(self.witness_socket.parent)
        if self.socket_path.exists() or self.socket_path.is_symlink():
            raise AdmissionDenied('socket path occupied')
        if self.local_db.exists(): secure_regular(self.local_db, os.geteuid())
        lock = self.local_db.with_suffix('.lock')
        if lock.exists(): secure_regular(lock, os.geteuid())
        if self.witness_socket.is_symlink() or not self.witness_socket.is_socket():
            raise AdmissionDenied('witness endpoint missing or invalid')
        if self.witness_uid is not None and self.witness_socket.stat().st_uid != self.witness_uid:
            raise AdmissionDenied('witness owner mismatch')
    def serve(self, ready=None, limit=None):
        self._preflight()
        # Recovery is required before publishing production socket.
        admission = AnchoredAdmission(self.local_db, self.witness_client_factory(self.witness_socket))
        admission.recover()
        os.chmod(self.local_db, 0o600)
        os.chmod(self.local_db.with_suffix('.lock'), 0o600)
        self._preflight()
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            srv.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o660)
            srv.listen(16)
            srv.settimeout(0.5)
            if ready is not None: ready.set()
            count = 0
            while limit is None or count < limit:
                try: client, _ = srv.accept()
                except socket.timeout: continue
                count += 1
                with client:
                    client.settimeout(3)
                    try:
                        if peer_uid(client) not in self.client_uids:
                            raise AdmissionDenied('client UID rejected')
                        request = _receive(client)
                        if type(request) is not dict or set(request) != {'operation', 'payload'}:
                            raise AdmissionDenied('invalid request shape')
                        if request['operation'] != 'admit' or type(request['payload']) is not str:
                            raise AdmissionDenied('unsupported operation')
                        if len(request['payload']) > MAX_PAYLOAD * 2:
                            raise AdmissionDenied('oversize payload')
                        try: payload = bytes.fromhex(request['payload'])
                        except ValueError: raise AdmissionDenied('invalid payload encoding')
                        if len(payload) > MAX_PAYLOAD: raise AdmissionDenied('oversize payload')
                        self._preflight_runtime()
                        result = admission.admit(payload)
                        _send(client, {'ok': True, 'result': result})
                    except (AdmissionDenied, OSError, ValueError) as exc:
                        try: _send(client, {'ok': False, 'reason': str(exc)})
                        except OSError: pass
        finally:
            srv.close()
            if self.socket_path.is_socket(): self.socket_path.unlink()
    def _preflight_runtime(self):
        secure_regular(self.local_db, os.geteuid())
        secure_regular(self.local_db.with_suffix('.lock'), os.geteuid())
        if self.witness_socket.is_symlink() or not self.witness_socket.is_socket():
            raise AdmissionDenied('witness endpoint changed')
        if self.witness_uid is not None and self.witness_socket.stat().st_uid != self.witness_uid:
            raise AdmissionDenied('witness endpoint owner changed')

class ProductionAdmissionClient:
    def __init__(self, socket_path): self.socket_path = str(socket_path)
    def admit(self, payload):
        if type(payload) is not bytes or len(payload) > MAX_PAYLOAD:
            raise AdmissionDenied('invalid payload')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            try:
                sock.connect(self.socket_path)
                _send(sock, {'operation': 'admit', 'payload': payload.hex()})
                result = _receive(sock)
            except OSError as exc:
                raise AdmissionDenied('production IPC unavailable') from exc
            if type(result) is not dict or result.get('ok') is not True:
                raise AdmissionDenied(result.get('reason', 'invalid response') if type(result) is dict else 'invalid response')
            if result['result'].get('engineering_approval') != 'BLOCKED/NO-GO':
                raise AdmissionDenied('unexpected readiness state')
            return result['result']
