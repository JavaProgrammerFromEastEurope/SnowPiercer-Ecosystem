"""ISLAND-GEO-022: signed challenge-bound root protocol and lab-only root service.

The SoftwareRootServer is explicitly ROLLBACKABLE and MUST NEVER authorize GO.
RootClient checks kernel peer UID and a pinned Ed25519 public key, not only UID.
Production demands an independently assessed, hardware-backed monotonic root.
"""
import json
import os
import secrets
import signal
import socket
import sqlite3
import stat
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .anchored_admission import AdmissionDenied, WitnessStore, GENESIS, _send, _receive
from .attested_broker import _canonical, _strict_hex, _read_private_file
from .production_admission import peer_uid, secure_directory
from .mandatory_guard import _safe_existing

DOMAIN = b'ISLAND-GEO-022:ROOT-HEAD:V1\0'


def _head(head):
    if (type(head) is not dict or set(head) != {'sequence', 'digest'}
            or type(head['sequence']) is not int or head['sequence'] < 0
            or type(head['digest']) is not str):
        raise AdmissionDenied('invalid monotonic head')
    _strict_hex(head['digest'], 64)
    if head['sequence'] == 0 and head['digest'] != GENESIS:
        raise AdmissionDenied('invalid genesis anchor')
    return head


def prove(head, challenge, signing_key):
    """Lab utility. Never accepts unsigned or unbound root responses."""
    _head(head)
    _strict_hex(challenge, 32)
    body = {'protocol': 'ISLAND-GEO-022-root-v1', 'challenge': challenge, 'head': head}
    return {'body': body, 'signature': signing_key.sign(DOMAIN + _canonical(body)).hex()}


def verify_proof(proof, challenge, public_key):
    if type(proof) is not dict or set(proof) != {'body', 'signature'}:
        raise AdmissionDenied('root proof shape')
    body = proof['body']
    if (type(body) is not dict or set(body) != {'protocol', 'challenge', 'head'}
            or body['protocol'] != 'ISLAND-GEO-022-root-v1'
            or body['challenge'] != challenge):
        raise AdmissionDenied('root proof challenge mismatch')
    _strict_hex(challenge, 32)
    _head(body['head'])
    sig = _strict_hex(proof['signature'], 128)
    if type(public_key) is not bytes or len(public_key) != 32:
        raise AdmissionDenied('untrusted root key')
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(sig, DOMAIN + _canonical(body))
    except (InvalidSignature, ValueError) as exc:
        raise AdmissionDenied('invalid root attestation signature') from exc
    return body['head']


class RootClient:
    """Signed, nonce-fresh remote root; transport authentication is SO_PEERCRED."""
    def __init__(self, endpoint, root_uid, public_key):
        if type(root_uid) is not int or root_uid <= 0:
            raise AdmissionDenied('invalid root UID')
        self.endpoint = str(endpoint)
        self.root_uid = root_uid
        self.public_key = public_key

    def execute(self, operation, record=None):
        if operation not in ('read', 'cas'):
            raise AdmissionDenied('unknown root operation')
        challenge = secrets.token_hex(16)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(3)
            conn.connect(self.endpoint)
            if peer_uid(conn) != self.root_uid:
                raise AdmissionDenied('independent root peer UID mismatch')
            _send(conn, {'operation': operation, 'record': record, 'challenge': challenge})
            response = _receive(conn)
        if type(response) is not dict or response.get('ok') is not True:
            raise AdmissionDenied('monotonic root denied or missing')
        head = verify_proof(response.get('proof'), challenge, self.public_key)
        if operation == 'cas' and (head['sequence'], head['digest']) != (record['sequence'], record['digest']):
            raise AdmissionDenied('root CAS did not advance')
        return head

    def require_head(self, expected):
        head = self.execute('read')
        if _head(expected) != head:
            raise AdmissionDenied('independent root and witness divergence')
        return head


class SoftwareRootServer:
    """LAB ONLY: sqlite root and software key can both roll back. Always NO-GO."""
    def __init__(self, endpoint, db, private_key_path, witness_uid, crash_at=None):
        self.endpoint = Path(endpoint)
        self.db = Path(db)
        self.private_key_path = Path(private_key_path)
        self.witness_uid = witness_uid
        if crash_at not in (None, 'before_root_cas', 'after_root_cas'):
            raise AdmissionDenied('unknown root crash point')
        self.crash_at = crash_at

    def serve(self):
        uid = os.geteuid()
        if uid <= 0 or self.witness_uid <= 0 or uid == self.witness_uid:
            raise AdmissionDenied('distinct unprivileged root emulator UID required')
        secure_directory(self.db.parent, uid)
        for path in (self.db, self.private_key_path, self.db.with_suffix('.lock')):
            _safe_existing(path, uid)
        signing = Ed25519PrivateKey.from_private_bytes(_read_private_file(self.private_key_path, uid, 32))
        ns = self.endpoint.parent.lstat()
        if (not stat.S_ISDIR(ns.st_mode) or ns.st_uid != 0 or not ns.st_mode & stat.S_ISVTX
                or ns.st_mode & 0o777 != 0o777):
            raise AdmissionDenied('root-owned sticky IPC namespace required')
        if self.endpoint.exists() or self.endpoint.is_symlink():
            raise AdmissionDenied('occupied root endpoint')
        store = WitnessStore(self.db)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(self.endpoint))
            os.chmod(self.endpoint, 0o660)
            server.listen(16)
            server.settimeout(.3)
            try:
                while True:
                    try:
                        conn, _ = server.accept()
                    except socket.timeout:
                        continue
                    with conn:
                        conn.settimeout(3)
                        try:
                            if peer_uid(conn) != self.witness_uid:
                                raise AdmissionDenied('untrusted root caller UID')
                            request = _receive(conn)
                            if type(request) is not dict or set(request) != {'operation','record','challenge'}:
                                raise AdmissionDenied('bad root request')
                            challenge = request['challenge']
                            _strict_hex(challenge, 32)
                            operation = request['operation']
                            if operation == 'cas' and self.crash_at == 'before_root_cas':
                                os.kill(os.getpid(), signal.SIGKILL)
                            head = store.execute(operation, request['record'])
                            if operation == 'cas' and self.crash_at == 'after_root_cas':
                                os.kill(os.getpid(), signal.SIGKILL)
                            _send(conn, {'ok': True, 'proof': prove(head, challenge, signing)})
                        except (AdmissionDenied, ValueError, OSError, sqlite3.Error) as exc:
                            try:
                                _send(conn, {'ok': False, 'reason': str(exc)})
                            except OSError:
                                pass
            finally:
                if self.endpoint.is_socket() and self.endpoint.stat().st_uid == uid:
                    self.endpoint.unlink()
