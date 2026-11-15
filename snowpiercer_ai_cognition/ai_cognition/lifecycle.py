"""AI-CORE-003: durable rotation journal and fail-closed replay admission.

The anchor is a separately provisioned monotonic counter, not a hardware root of trust.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import threading
from pathlib import Path

from .admission import AdmissionRejected, ReplayStore, TrustedAdmission


class RecoveryRequired(AdmissionRejected):
    pass


def _digest(source, generation, key):
    return hmac.new(key, (source + ':' + str(generation)).encode(), hashlib.sha256).hexdigest()


class RotationManager:
    """SQLite journal with independent counter anchor; callers provision keys externally.

    The anchor must live in a separate protected failure/rollback domain. Rotation
    can fail closed after a crash and requires explicit reconciliation.
    """
    def __init__(self, store: ReplayStore, anchor_path: str, keys: dict, *, bootstrap=False):
        if not isinstance(store, ReplayStore) or not keys or any(not isinstance(k, str) or not isinstance(v, bytes) or len(v) < 32 for k, v in keys.items()):
            raise ValueError('invalid store or keys')
        self.store = store
        self.anchor = Path(anchor_path)
        self.keys = dict(keys)
        self.lock = threading.RLock()
        with store._lock:
            db = store._db
            db.execute('CREATE TABLE IF NOT EXISTS rotation (source TEXT PRIMARY KEY, generation INTEGER NOT NULL, fingerprint TEXT NOT NULL, phase TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS lifecycle_anchor (id INTEGER PRIMARY KEY CHECK(id=1), path TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO lifecycle_anchor VALUES (1,?)', (str(self.anchor.resolve()),))
            db.execute('CREATE TABLE IF NOT EXISTS lifecycle_meta (id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO lifecycle_meta VALUES (1,0)')
        if bootstrap:
            with store._lock:
                if self._epoch() != 0 or self.anchor.exists() or store._db.execute('SELECT 1 FROM seen LIMIT 1').fetchone() or store._db.execute('SELECT 1 FROM rotation LIMIT 1').fetchone():
                    raise RecoveryRequired('BOOTSTRAP_NOT_ALLOWED')
            self.initialize_anchor()
        self._check()

    def _epoch(self):
        return self.store._db.execute('SELECT epoch FROM lifecycle_meta WHERE id=1').fetchone()[0]

    def _anchor_read(self):
        try:
            raw = self.anchor.read_text(encoding='ascii')
            if not raw.endswith('\n') or not raw[:-1].isdigit() or len(raw) > 22:
                raise ValueError('anchor format')
            return int(raw[:-1])
        except (OSError, ValueError) as exc:
            raise RecoveryRequired('ANCHOR_UNAVAILABLE') from exc

    def initialize_anchor(self):
        """One-time provisioning only: refuses overwrites or existing advanced epochs."""
        with self.lock, self.store._lock:
            if self._epoch() != 0 or self.anchor.exists():
                raise RecoveryRequired('ANCHOR_ALREADY_PROVISIONED')
            self._write_anchor(0, exclusive=True)

    def _write_anchor(self, epoch, exclusive=False):
        self.anchor.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.anchor.with_name(self.anchor.name + '.pending')
        flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
        fd = os.open(str(tmp), flags, 0o600)
        try:
            with os.fdopen(fd, 'w', encoding='ascii') as f:
                f.write(str(epoch) + '\n')
                f.flush()
                os.fsync(f.fileno())
            if exclusive and self.anchor.exists():
                raise RecoveryRequired('ANCHOR_ALREADY_PROVISIONED')
            os.replace(str(tmp), str(self.anchor))
            dirfd = os.open(str(self.anchor.parent), os.O_RDONLY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        finally:
            if tmp.exists():
                tmp.unlink()

    def _check(self):
        with self.lock, self.store._lock:
            try:
                epoch = self._epoch()
                anchor = self._anchor_read()
                phases = self.store._db.execute("SELECT source, generation, fingerprint, phase FROM rotation").fetchall()
                if anchor != epoch:
                    raise RecoveryRequired('EPOCH_MISMATCH')
                if any(p != 'ACTIVE' for _, _, _, p in phases):
                    raise RecoveryRequired('ROTATION_INCOMPLETE')
                for source, generation, fingerprint, _ in phases:
                    key = self.keys.get(source)
                    if key is None or not hmac.compare_digest(_digest(source, generation, key), fingerprint):
                        raise RecoveryRequired('KEY_MISMATCH')
            except sqlite3.Error as exc:
                raise RecoveryRequired('LIFECYCLE_STORE_UNAVAILABLE') from exc

    def provision(self, source):
        """Provision initial generation before admitting events."""
        with self.lock, self.store._lock:
            self._check()
            if source not in self.keys:
                raise ValueError('unknown source')
            db = self.store._db
            if db.execute('SELECT 1 FROM rotation WHERE source=?', (source,)).fetchone():
                raise ValueError('already provisioned')
            db.execute('INSERT INTO rotation VALUES (?,?,?,?)', (source, 1, _digest(source, 1, self.keys[source]), 'ACTIVE'))

    def rotate(self, source, new_key, fault=None):
        """Fences admission before rotating. Fault hooks simulate process crashes."""
        if not isinstance(new_key, bytes) or len(new_key) < 32:
            raise ValueError('invalid key')
        with self.lock, self.store._lock:
            self._check()
            db = self.store._db
            row = db.execute('SELECT generation FROM rotation WHERE source=?', (source,)).fetchone()
            if row is None:
                raise ValueError('unprovisioned source')
            generation = row[0] + 1
            # Phase 1 durable fence, before key transition.
            db.execute("UPDATE rotation SET phase='PREPARED' WHERE source=?", (source,))
            if fault == 'prepared':
                raise RuntimeError('simulated crash after prepare')
            # Phase 2 commit new generation and increment epoch atomically.
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('UPDATE rotation SET generation=?, fingerprint=?, phase=? WHERE source=?',
                           (generation, _digest(source, generation, new_key), 'COMMITTED', source))
                db.execute('UPDATE lifecycle_meta SET epoch=epoch+1 WHERE id=1')
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
            if fault == 'committed':
                raise RuntimeError('simulated crash after commit')
            self._write_anchor(self._epoch())
            if fault == 'anchored':
                raise RuntimeError('simulated crash after anchor')
            self.keys[source] = new_key
            db.execute("UPDATE rotation SET phase='ACTIVE' WHERE source=?", (source,))
            self._check()

    def recover(self, source, key, *, approved=False):
        """Explicit operator reconciliation. Never automatically lowers anchor epoch."""
        if not approved or not isinstance(key, bytes) or len(key) < 32:
            raise RecoveryRequired('RECOVERY_NOT_AUTHORIZED')
        with self.lock, self.store._lock:
            db = self.store._db
            row = db.execute('SELECT generation,fingerprint,phase FROM rotation WHERE source=?', (source,)).fetchone()
            if row is None or row[2] == 'ACTIVE':
                raise RecoveryRequired('NO_PENDING_ROTATION')
            if not hmac.compare_digest(row[1], _digest(source, row[0], key)):
                raise RecoveryRequired('KEY_MISMATCH')
            epoch = self._epoch()
            anchor = self._anchor_read()
            if anchor > epoch:
                raise RecoveryRequired('ROLLBACK_DETECTED')
            if anchor < epoch:
                # Operator must independently verify database integrity and replay history.
                raise RecoveryRequired('ANCHOR_RECONCILIATION_REQUIRED')
            self.keys[source] = key
            db.execute("UPDATE rotation SET phase='ACTIVE' WHERE source=?", (source,))
            self._check()

    def admit(self, envelope, *, clock=None):
        with self.lock, self.store._lock:
            self._check()
            return TrustedAdmission(self.keys, self.store, clock=clock).admit(envelope)
