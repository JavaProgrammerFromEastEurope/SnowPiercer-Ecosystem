"""RAIL-TRUST-014: independently UID-owned, durable *local laboratory* authorities.

This implementation proves SQLite transactional persistence across process death,
NOT protection against rollback of a complete disk image, a compromised owner UID,
or host administrators. It is intentionally barred from production deployment.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import sqlite3
import stat
import struct
import sys
from pathlib import Path

DOMAIN = 'snowpiercer.railsystem.provider.v1'
LIMIT = 4096


class AuthorityDenied(RuntimeError):
    pass


def _dir(path: Path, *, gid: int, mode: int):
    if not path.is_absolute():
        raise AuthorityDenied('absolute authority directory required')
    s = path.lstat()
    if (not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid()
            or s.st_gid != gid or stat.S_IMODE(s.st_mode) != mode):
        raise AuthorityDenied('authority directory owner/group/mode mismatch')


def _db_file(path: Path):
    s = path.lstat()
    if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid()
            or s.st_nlink != 1 or stat.S_IMODE(s.st_mode) != 0o600):
        raise AuthorityDenied('authority database not protected')


def _connect(path: Path):
    _db_file(path)
    conn = sqlite3.connect(path, isolation_level=None, timeout=2)
    try:
        conn.execute('PRAGMA journal_mode=DELETE')
        conn.execute('PRAGMA synchronous=FULL')
        if conn.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise AuthorityDenied('invalid authority database')
        return conn
    except BaseException:
        conn.close()
        raise


class LocalDurableAuthority:
    """Lab-only witness or permit authority run as its own dedicated Linux UID.

    Creates NO state at runtime. Provisioning must be explicit and cannot reset
    an existing authority. Socket path is never unlinked after abrupt death.
    """
    def __init__(self, kind, state_dir, ipc_dir, *, transport_gid, service_uid):
        if kind not in ('anchor', 'permit'):
            raise AuthorityDenied('invalid authority role')
        if (type(transport_gid) is not int or transport_gid <= 0 or
                type(service_uid) is not int or service_uid <= 0 or
                os.geteuid() in (0, service_uid)):
            raise AuthorityDenied('distinct non-root authority and service UIDs required')
        self.kind = kind
        self.state_dir = Path(state_dir)
        self.ipc_dir = Path(ipc_dir)
        self.gid = transport_gid
        self.service_uid = service_uid
        self.db = self.state_dir / ('witness.sqlite3' if kind == 'anchor' else 'permits.sqlite3')
        self.path = self.ipc_dir / 'provider.sock'
        self.sock = None
        self.identity = None

    def _directories(self):
        _dir(self.state_dir, gid=self.gid, mode=0o700)
        _dir(self.ipc_dir, gid=self.gid, mode=0o750)
        if self.state_dir == self.ipc_dir:
            raise AuthorityDenied('state and IPC directories must be separate')

    def provision(self):
        self._directories()
        if os.path.lexists(self.db):
            raise AuthorityDenied('already provisioned; no implicit reset')
        # No symbolic link, and the parent is private to this UID.
        fd = os.open(self.db, os.O_RDWR | os.O_CREAT | os.O_EXCL |
                     getattr(os, 'O_NOFOLLOW', 0), 0o600)
        os.close(fd)
        conn = _connect(self.db)
        try:
            conn.execute('BEGIN IMMEDIATE')
            if self.kind == 'anchor':
                conn.execute('CREATE TABLE witness (id INTEGER PRIMARY KEY CHECK(id=1), sequence INTEGER NOT NULL, nonce TEXT NOT NULL)')
                conn.execute("INSERT INTO witness VALUES (1,0,'')")
            else:
                conn.execute('CREATE TABLE permits (digest TEXT PRIMARY KEY, sequence INTEGER NOT NULL, action TEXT NOT NULL)')
            conn.execute('COMMIT')
        except BaseException:
            if conn.in_transaction:
                conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()
        dfd = os.open(self.state_dir, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try: os.fsync(dfd)
        finally: os.close(dfd)

    def _verify_socket(self):
        s = self.path.lstat()
        if (not stat.S_ISSOCK(s.st_mode) or s.st_uid != os.geteuid() or
                s.st_gid != self.gid or stat.S_IMODE(s.st_mode) != 0o660 or
                (s.st_dev, s.st_ino) != self.identity):
            raise AuthorityDenied('IPC path changed')

    def start(self):
        self._directories()
        conn = _connect(self.db)
        try:
            if self.kind == 'anchor':
                rows = conn.execute('SELECT sequence,nonce FROM witness').fetchall()
                if len(rows) != 1 or type(rows[0][0]) is not int or rows[0][0] < 0 or not isinstance(rows[0][1], str):
                    raise AuthorityDenied('corrupt witness record')
            else:
                conn.execute('SELECT digest FROM permits LIMIT 1').fetchall()
        finally:
            conn.close()
        if os.path.lexists(self.path):
            raise AuthorityDenied('socket occupied; after crash require operator reconciliation')
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.path))
            os.chmod(self.path, 0o660)
            s = self.path.lstat()
            self.identity = (s.st_dev, s.st_ino)
            self._verify_socket()
            listener.listen(8)
            listener.settimeout(0.25)
            self.sock = listener
        except BaseException:
            listener.close()
            self._remove_owned()
            raise

    def _remove_owned(self):
        if self.identity is not None:
            try:
                self._verify_socket()
            except (OSError, AuthorityDenied):
                return
            self.path.unlink()
            self.identity = None

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        self._remove_owned()

    def _process(self, request, *, kill_at=None):
        if (type(request) is not dict or request.get('domain') != DOMAIN or
                request.get('kind') != self.kind):
            raise AuthorityDenied('wrong request envelope')
        operation = request.get('operation')
        if self.kind == 'anchor':
            if operation == 'read' and set(request) == {'domain', 'kind', 'operation'}:
                conn = _connect(self.db)
                try:
                    seq, nonce = conn.execute('SELECT sequence,nonce FROM witness WHERE id=1').fetchone()
                    return {'sequence': seq, 'nonce': nonce}
                finally:
                    conn.close()
            if operation != 'advance' or set(request) != {'domain', 'kind', 'operation', 'expected', 'next'}:
                raise AuthorityDenied('unsupported witness operation')
            expected, target = request['expected'], request['next']
            if not all(type(x) is list and len(x) == 2 and type(x[0]) is int and x[0] >= 0
                       and isinstance(x[1], str) and len(x[1]) <= 128 for x in (expected, target)):
                raise AuthorityDenied('invalid CAS arguments')
            if target[0] <= expected[0]:
                raise AuthorityDenied('non-monotonic CAS')
            conn = _connect(self.db)
            try:
                conn.execute('BEGIN IMMEDIATE')
                current = conn.execute('SELECT sequence,nonce FROM witness WHERE id=1').fetchone()
                advanced = list(current) == expected
                if advanced:
                    conn.execute('UPDATE witness SET sequence=?,nonce=? WHERE id=1', target)
                if kill_at == 'before_commit': os.kill(os.getpid(), signal.SIGKILL)
                conn.execute('COMMIT')
                if kill_at == 'after_commit': os.kill(os.getpid(), signal.SIGKILL)
                return {'advanced': advanced}
            except BaseException:
                if conn.in_transaction: conn.execute('ROLLBACK')
                raise
            finally:
                conn.close()
        if operation == 'ready' and set(request) == {'domain', 'kind', 'operation'}:
            conn = _connect(self.db)
            conn.close()
            return {'ready': True}
        if operation != 'consume' or set(request) != {'domain', 'kind', 'operation', 'digest', 'sequence', 'action'}:
            raise AuthorityDenied('unsupported permit operation')
        digest, sequence, action = request['digest'], request['sequence'], request['action']
        if (type(digest) is not str or re.fullmatch(r'[0-9a-f]{64}', digest) is None or
                type(sequence) is not int or sequence < 1 or action != 'reconcile'):
            raise AuthorityDenied('invalid permit consumption')
        conn = _connect(self.db)
        try:
            conn.execute('BEGIN IMMEDIATE')
            consumed = conn.execute('SELECT 1 FROM permits WHERE digest=?', (digest,)).fetchone() is None
            if consumed:
                conn.execute('INSERT INTO permits VALUES (?,?,?)', (digest, sequence, action))
            if kill_at == 'before_commit': os.kill(os.getpid(), signal.SIGKILL)
            conn.execute('COMMIT')
            if kill_at == 'after_commit': os.kill(os.getpid(), signal.SIGKILL)
            return {'consumed': consumed}
        except BaseException:
            if conn.in_transaction: conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()

    def handle_one(self, *, kill_at=None):
        if self.sock is None:
            raise AuthorityDenied('authority not running')
        self._verify_socket()
        conn, _ = self.sock.accept()
        with conn:
            conn.settimeout(2)
            try:
                if not hasattr(socket, 'SO_PEERCRED'):
                    raise AuthorityDenied('kernel credentials unavailable')
                credentials = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if credentials[1] != self.service_uid:
                    raise AuthorityDenied('unauthorized IPC caller UID')
                self._verify_socket()
                raw = bytearray()
                while len(raw) < LIMIT and b'\n' not in raw:
                    part = conn.recv(min(1024, LIMIT-len(raw)))
                    if not part: break
                    raw.extend(part)
                if not raw.endswith(b'\n') or len(raw) > LIMIT or b'\n' in raw[:-1]:
                    raise AuthorityDenied('malformed IPC frame')
                request = json.loads(raw)
                answer = {'domain': DOMAIN, 'kind': self.kind, 'operation': request.get('operation'), 'status': 'OK'}
                answer.update(self._process(request, kill_at=kill_at))
            except (AuthorityDenied, OSError, ValueError, TypeError, sqlite3.Error, TimeoutError, AttributeError):
                answer = {'domain': DOMAIN, 'kind': self.kind, 'operation': 'invalid', 'status': 'DENIED'}
            try: conn.sendall((json.dumps(answer, sort_keys=True)+'\n').encode())
            except (OSError, TimeoutError): pass

    def serve(self, *, kill_at=None):
        self.start()
        stopping = False
        def term(_sig, _frame):
            nonlocal stopping
            stopping = True
        previous = signal.signal(signal.SIGTERM, term)
        try:
            while not stopping:
                try: self.handle_one(kill_at=kill_at)
                except TimeoutError: continue
        finally:
            signal.signal(signal.SIGTERM, previous)
            self.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Local test-only durable authority, never a production witness')
    parser.add_argument('--kind', choices=('anchor', 'permit'), required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--ipc-dir', type=Path, required=True)
    parser.add_argument('--transport-gid', type=int, required=True)
    parser.add_argument('--service-uid', type=int, required=True)
    parser.add_argument('--provision', action='store_true')
    parser.add_argument('--test-only-serve', action='store_true')
    args = parser.parse_args(argv)
    if args.provision == args.test_only_serve:
        parser.error('choose exactly one explicit laboratory operation')
    try:
        authority = LocalDurableAuthority(args.kind, args.state_dir, args.ipc_dir,
            transport_gid=args.transport_gid, service_uid=args.service_uid)
        if args.provision: authority.provision()
        else: authority.serve()
        return 0
    except (AuthorityDenied, OSError, sqlite3.Error) as exc:
        print(f'RAIL-TRUST-014 BLOCKED: {type(exc).__name__}', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
