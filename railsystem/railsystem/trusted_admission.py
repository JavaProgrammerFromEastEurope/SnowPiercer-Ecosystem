"""RAIL-TRUST-002: transactional software-release admission (not train control)."""
from __future__ import annotations
import json
import os
import sqlite3
import stat
from pathlib import Path
from .trust import verify_attestation, TrustError
from .release_gate import evaluate

class AdmissionError(ValueError):
    pass

def _secure_file(path: Path, *, create=False):
    path = Path(path)
    if path.is_symlink():
        raise AdmissionError('symlink prohibited')
    if create and not path.exists():
        parent = path.parent.resolve(strict=True)
        if parent.is_symlink() or (parent.stat().st_mode & 0o022):
            raise AdmissionError('unsafe state directory')
        return
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o022 or info.st_uid != os.geteuid():
        raise AdmissionError('unsafe owner, permissions, or file type')

def read_protected_json(path: Path):
    _secure_file(path)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise AdmissionError('unsafe opened file')
        with os.fdopen(fd, 'r', encoding='utf-8') as handle:
            fd = -1
            return json.load(handle)
    finally:
        if fd >= 0:
            os.close(fd)

def admit(root: Path, *, baseline: dict, attestation: dict, trust: dict, db_path: Path,
          regression: dict | None = None, fault: str | None = None) -> dict:
    """BEGIN IMMEDIATE serializes verification and state commit across processes.

    Database and trust root must be provisioned in a protected directory. The
    return value is a software gate only, never authorization to operate a train.
    """
    db_path = Path(db_path)
    _secure_file(db_path, create=True)
    conn = sqlite3.connect(str(db_path), timeout=15, isolation_level=None)
    try:
        conn.execute('PRAGMA busy_timeout=15000')
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('PRAGMA journal_mode=DELETE')
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('CREATE TABLE IF NOT EXISTS replay_state (id INTEGER PRIMARY KEY CHECK(id=1), sequence INTEGER NOT NULL CHECK(sequence>=0), nonces TEXT NOT NULL)')
        conn.execute("INSERT OR IGNORE INTO replay_state VALUES (1,0,'[]')")
        sequence, raw = conn.execute('SELECT sequence,nonces FROM replay_state WHERE id=1').fetchone()
        used = json.loads(raw)
        if not isinstance(used, list):
            raise AdmissionError('corrupt replay state')
        state = {'schema_version': 1, 'minimum_sequence': sequence, 'used_nonces': used}
        verified = verify_attestation(root, baseline, attestation, trust, state)
        # No caller-provided regression can grant admission: run the suite locally.
        gate = evaluate(root, expected_manifest=baseline['manifest'], regression=None)
        if gate['status'] != 'PASS':
            raise AdmissionError('release checks failed: ' + gate['status'])
        if fault == 'before_commit':
            os._exit(87)
        next_state = verified['next_state']
        conn.execute('UPDATE replay_state SET sequence=?,nonces=? WHERE id=1',
                     (next_state['minimum_sequence'], json.dumps(next_state['used_nonces'])))
        if fault == 'after_write':
            os._exit(88)
        conn.execute('COMMIT')
        return {'stage': 'RAIL-TRUST-002', 'status': 'PASS', 'sequence': next_state['minimum_sequence'],
                'scope': 'software release admission only; not physical operations authorization'}
    except BaseException:
        if conn.in_transaction:
            conn.execute('ROLLBACK')
        raise
    finally:
        conn.close()

def assess_admission(root: Path, *, baseline=None, attestation=None, trust=None, db_path=None) -> dict:
    if any(x is None for x in (baseline, attestation, trust, db_path)):
        return {'stage': 'RAIL-TRUST-002', 'status': 'BLOCKED', 'reason': 'independent trust inputs and persistent state required'}
    try:
        return admit(root, baseline=baseline, attestation=attestation, trust=trust, db_path=db_path)
    except (AdmissionError, TrustError, OSError, ValueError, sqlite3.Error) as exc:
        return {'stage': 'RAIL-TRUST-002', 'status': 'FAIL', 'reason': str(exc)}
