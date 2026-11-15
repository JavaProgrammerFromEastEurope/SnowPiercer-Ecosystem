"""LIFE-CORE-008: fail-closed inspection of opt-in protected SQLite journal.

Not a boundary against a database administrator who can modify both schema and seal.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from .admission import AdmittedLifecycle, AdmissionError

GUARDS = {
    'ls_guard_insert': "CREATE TRIGGER ls_guard_insert BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'LIFE_FENCE_REQUIRED') WHERE ls_admitted() != 1; END",
    'ls_guard_update': "CREATE TRIGGER ls_guard_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'LIFE_EVENT_IMMUTABLE'); END",
    'ls_guard_delete': "CREATE TRIGGER ls_guard_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'LIFE_EVENT_IMMUTABLE'); END",
}

def normalize(sql):
    return ' '.join(sql.strip().split()).casefold()

def guard_digest():
    return hashlib.sha256(json.dumps({k:normalize(v) for k,v in sorted(GUARDS.items())},sort_keys=True,separators=(',',':')).encode()).hexdigest()

def inspect_v2_admission(db):
    """Shared admission gate used by v2-aware legacy admitted writers."""
    table=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='life_admission'").fetchone()
    if not table:
        return
    row=db.execute('SELECT version FROM life_admission WHERE singleton=1').fetchone()
    if not row or row[0] not in (1,2):
        raise AdmissionError('invalid admission version')
    if row[0]==2:
        guards=dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='events'"))
        if any(normalize(guards.get(name,''))!=normalize(sql) for name,sql in GUARDS.items()):
            raise AdmissionError('v2 admission guard altered')
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='life_guard_seal'").fetchone():
            raise AdmissionError('v2 seal missing')
        if db.execute('SELECT singleton,digest FROM life_guard_seal').fetchall()!=[(1,guard_digest())]:
            raise AdmissionError('v2 seal mismatch')

class HardenedLifecycle(AdmittedLifecycle):
    """Verify sealed v2 schema on open and before every protected write.

    Explicit `harden(token)` migrates an existing v1 journal. Unprotected
    journals remain compatible until explicitly protected.
    """
    def __init__(self, registry, path, *, clock_ns=None):
        super().__init__(registry,path,clock_ns=clock_ns)
        try:
            self.verify_integrity()
        except Exception:
            self.close()
            raise

    def _version(self):
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='life_admission'").fetchone():
            return None
        rows=self.db.execute('SELECT singleton,version FROM life_admission').fetchall()
        if len(rows)!=1 or rows[0][0]!=1 or rows[0][1] not in (1,2):
            raise AdmissionError('invalid admission configuration')
        return rows[0][1]

    def verify_integrity(self):
        version=self._version()
        if version is None:
            # Fail closed on orphan guards even if admission metadata is missing.
            names={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='events'")}
            if names.intersection(GUARDS):
                raise AdmissionError('orphan admission triggers')
            return {'protected':False,'version':None}
        rows=dict(self.db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='events'"))
        for name,sql in GUARDS.items():
            if name not in rows or normalize(rows[name])!=normalize(sql):
                raise AdmissionError('missing or altered guard: '+name)
        if version==2:
            if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='life_guard_seal'").fetchone():
                raise AdmissionError('missing guard seal table')
            seals=self.db.execute('SELECT singleton,digest FROM life_guard_seal').fetchall()
            if seals!=[(1,guard_digest())]:
                raise AdmissionError('invalid guard seal')
        return {'protected':True,'version':version,'digest':guard_digest()}

    def harden(self, token):
        self._begin()
        try:
            self._check(token,self._now())
            status=self.verify_integrity()
            if not status['protected']:
                raise AdmissionError('protect with legacy API before hardening')
            self._replay()
            self.db.execute('CREATE TABLE IF NOT EXISTS life_guard_seal (singleton INTEGER PRIMARY KEY CHECK(singleton=1),digest TEXT NOT NULL)')
            self.db.execute('INSERT INTO life_guard_seal(singleton,digest) VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET digest=excluded.digest',(guard_digest(),))
            self.db.execute('UPDATE life_admission SET version=2 WHERE singleton=1')
            self._check(token,self._now())
            self.verify_integrity()
            self.db.execute('COMMIT')
        except Exception:
            self._rollback()
            raise

    def protect(self, token):
        self.verify_integrity()
        super().protect(token)
        self.verify_integrity()

    def transition(self, component_id, next_state, *, event_id, reason, actor, timestamp_utc=None, token=None):
        self.verify_integrity()
        return super().transition(component_id,next_state,event_id=event_id,reason=reason,actor=actor,timestamp_utc=timestamp_utc,token=token)

    def recover(self, *, token=None):
        self.verify_integrity()
        return super().recover(token=token)
