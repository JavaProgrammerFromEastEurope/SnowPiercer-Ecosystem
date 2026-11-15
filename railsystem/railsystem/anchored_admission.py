"""RAIL-TRUST-003: fail-closed, local filesystem anchor protocol.

Anchor is NOT a hardware-backed or independently administered monotonic counter.
"""
from __future__ import annotations
import contextlib
import fcntl
import json
import os
import sqlite3
import stat
import tempfile
from pathlib import Path
from .trusted_admission import AdmissionError, _secure_file
from .trust import verify_attestation
from .release_gate import evaluate

class RecoveryRequired(AdmissionError):
    pass


def _check_dir(directory):
    p = Path(directory)
    s = p.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid() or s.st_mode & 0o077:
        raise AdmissionError('private owner-controlled directory required')
    return p


def _read_anchor(path):
    _secure_file(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid() or s.st_nlink != 1 or s.st_mode & 0o077:
            raise AdmissionError('unsafe anchor')
        with os.fdopen(fd, 'r', encoding='utf8') as f:
            fd = -1
            value = json.load(f)
    finally:
        if fd >= 0: os.close(fd)
    if type(value) is not dict or set(value) != {'sequence', 'nonce'} or type(value['sequence']) is not int or value['sequence'] < 0 or not isinstance(value['nonce'], str):
        raise AdmissionError('invalid anchor')
    return value


def _atomic_anchor(path, value):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.anchor-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf8') as f:
            fd = -1
            json.dump(value, f, sort_keys=True)
            f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if fd >= 0: os.close(fd)
        if os.path.exists(name): os.unlink(name)


@contextlib.contextmanager
def _locked(directory):
    directory = _check_dir(directory)
    lock = directory / 'admission.lock'
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid() or s.st_nlink != 1 or s.st_mode & 0o077:
            raise AdmissionError('unsafe lock')
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _connect(directory):
    path = directory / 'admission.sqlite3'
    _secure_file(path, create=True)
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=15)
    try:
        conn.execute('PRAGMA journal_mode=DELETE')
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), sequence INTEGER NOT NULL, nonces TEXT NOT NULL, phase TEXT NOT NULL, pending_sequence INTEGER, pending_nonce TEXT)')
        conn.execute("INSERT OR IGNORE INTO state VALUES (1,0,'[]','IDLE',NULL,NULL)")
        conn.execute('COMMIT')
        return conn
    except BaseException:
        conn.close(); raise


def _state(conn):
    return conn.execute('SELECT sequence,nonces,phase,pending_sequence,pending_nonce FROM state WHERE id=1').fetchone()


def _assert_consistent(conn, anchor):
    seq, raw, phase, pending_seq, pending_nonce = _state(conn)
    if phase != 'IDLE' or pending_seq is not None or pending_nonce is not None:
        raise RecoveryRequired('unfinished transaction: offline recovery required')
    if seq != anchor['sequence']:
        raise RecoveryRequired('anchor/database disagreement')
    try: nonces = json.loads(raw)
    except (ValueError, TypeError) as exc: raise RecoveryRequired('invalid nonce ledger') from exc
    if not isinstance(nonces, list) or any(not isinstance(n, str) for n in nonces):
        raise RecoveryRequired('invalid nonce ledger')
    if seq and (not nonces or nonces[-1] != anchor['nonce']):
        raise RecoveryRequired('anchor nonce mismatch')
    return seq, nonces


def initialize(directory):
    """Provision only a new, empty, private state directory; never reset existing state."""
    directory = _check_dir(directory)
    with _locked(directory):
        if (directory / 'anchor.json').exists() or (directory / 'admission.sqlite3').exists():
            raise AdmissionError('already provisioned')
        _atomic_anchor(directory / 'anchor.json', {'sequence': 0, 'nonce': ''})
        conn = _connect(directory); conn.close()


def admit_anchored(root, *, baseline, attestation, trust, state_dir, fault=None):
    """Strict release admission. Caller must separately protect anchor from rollback."""
    directory = _check_dir(state_dir)
    with _locked(directory):
        anchor = _read_anchor(directory / 'anchor.json')
        conn = _connect(directory)
        try:
            seq, nonces = _assert_consistent(conn, anchor)
            verified = verify_attestation(root, baseline, attestation, trust, {'schema_version': 1, 'minimum_sequence': seq, 'used_nonces': nonces})
            gate = evaluate(root, expected_manifest=baseline['manifest'], regression=None)
            if gate['status'] != 'PASS': raise AdmissionError('release checks failed')
            nxt = verified['next_state']; newseq = nxt['minimum_sequence']; nonce = nxt['used_nonces'][-1]
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("UPDATE state SET phase='PREPARED',pending_sequence=?,pending_nonce=? WHERE id=1", (newseq, nonce))
            conn.execute('COMMIT')
            if fault == 'after_prepare': os._exit(91)
            _atomic_anchor(directory / 'anchor.json', {'sequence': newseq, 'nonce': nonce})
            if fault == 'after_anchor': os._exit(92)
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("UPDATE state SET sequence=?,nonces=?,phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1", (newseq, json.dumps(nxt['used_nonces'])))
            conn.execute('COMMIT')
            return {'stage': 'RAIL-TRUST-003', 'status': 'PASS', 'sequence': newseq, 'scope': 'software only'}
        finally:
            conn.close()


def recover(directory, *, permit):
    """Offline reconciliation; permit is caller-provided, not independently authenticated.

    Refuse to advance anchor from DB. Permit is consumed in SQLite transaction.
    """
    directory = _check_dir(directory)
    if not isinstance(permit, str) or len(permit) < 24:
        raise AdmissionError('recovery permit required')
    with _locked(directory):
        anchor = _read_anchor(directory / 'anchor.json')
        conn = _connect(directory)
        try:
            conn.execute('CREATE TABLE IF NOT EXISTS permits (digest TEXT PRIMARY KEY)')
            import hashlib
            digest = hashlib.sha256(permit.encode()).hexdigest()
            if conn.execute('SELECT 1 FROM permits WHERE digest=?', (digest,)).fetchone():
                raise AdmissionError('reused permit')
            seq, raw, phase, pending_seq, pending_nonce = _state(conn)
            if phase != 'PREPARED' or type(pending_seq) is not int or not isinstance(pending_nonce, str):
                raise RecoveryRequired('no valid prepared recovery transaction')
            if pending_seq <= seq: raise RecoveryRequired('invalid pending sequence')
            if anchor == {'sequence': seq, 'nonce': json.loads(raw)[-1] if seq else ''}:
                # The external anchor was not advanced: safely discard prepared request.
                conn.execute('BEGIN IMMEDIATE')
                conn.execute("UPDATE state SET phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1")
            elif anchor == {'sequence': pending_seq, 'nonce': pending_nonce}:
                conn.execute('BEGIN IMMEDIATE')
                nonces = json.loads(raw)
                if not isinstance(nonces, list): raise RecoveryRequired('invalid nonce ledger')
                conn.execute("UPDATE state SET sequence=?,nonces=?,phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1", (pending_seq, json.dumps(nonces + [pending_nonce])))
            else:
                raise RecoveryRequired('ambiguous anchor: manual investigation required')
            conn.execute('INSERT INTO permits VALUES (?)', (digest,))
            conn.execute('COMMIT')
            return {'status': 'RECOVERED', 'sequence': _state(conn)[0]}
        except BaseException:
            if conn.in_transaction: conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()
