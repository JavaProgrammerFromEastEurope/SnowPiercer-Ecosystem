"""Opt-in SQLite-local mandatory event write admission (not a hostile-DB-admin boundary)."""
import sqlite3
from pathlib import Path
from .coordination import FencedLifecycle, FencingError

class AdmissionError(FencingError):
    pass

class AdmittedLifecycle(FencedLifecycle):
    """Admit a fenced writer only during the validated SQLite transaction.

    Legacy writers can read and recover unprotected databases, but cannot append
    to a protected journal (SQLite UDF absent => trigger aborts).
    """
    def __init__(self, registry, path, *, clock_ns=None):
        self._admitted = False
        super().__init__(registry, path, clock_ns=clock_ns)
        self.db.create_function('ls_admitted', 0, lambda: int(self._admitted and self.db.in_transaction and not Path(str(self.path) + '.rotation-fence').exists()))

    def protect(self, token):
        """One-way opt-in migration, requires current lease and verified history."""
        self._begin()
        try:
            self._check(token, self._now())
            self._replay()
            self.db.execute('CREATE TABLE IF NOT EXISTS life_admission (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)')
            row = self.db.execute('SELECT version FROM life_admission WHERE singleton=1').fetchone()
            if row and row[0] != 1:
                raise AdmissionError('unknown admission version')
            if not row:
                self.db.execute('INSERT INTO life_admission VALUES (1,1)')
            # execute individual statements without executescript, preserving transaction
            self.db.execute("CREATE TRIGGER IF NOT EXISTS ls_guard_insert BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'LIFE_FENCE_REQUIRED') WHERE ls_admitted() != 1; END")
            self.db.execute("CREATE TRIGGER IF NOT EXISTS ls_guard_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'LIFE_EVENT_IMMUTABLE'); END")
            self.db.execute("CREATE TRIGGER IF NOT EXISTS ls_guard_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'LIFE_EVENT_IMMUTABLE'); END")
            self._check(token, self._now())
            self.db.execute('COMMIT')
        except Exception:
            self._rollback()
            raise

    def transition(self, component_id, next_state, *, event_id, reason, actor, timestamp_utc=None, token=None):
        # FencedLifecycle validates lease before and after append. Trigger checks
        # this admission flag within the same connection and transaction.
        # For v2 protected databases, even legacy admitted clients must fail
        # closed if the guard schema or configuration seal has been altered.
        from .hardening import inspect_v2_admission
        inspect_v2_admission(self.db)
        self._admitted = True
        try:
            return super().transition(component_id, next_state, event_id=event_id, reason=reason, actor=actor, timestamp_utc=timestamp_utc, token=token)
        finally:
            self._admitted = False
