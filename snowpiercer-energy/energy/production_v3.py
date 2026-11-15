"""CORE-011 opt-in fenced simulation entry point and durable recovery permits.

Not a trusted hardware boundary. Legacy direct ledger calls remain available.
"""
import os
import secrets
from contextlib import closing
import sqlite3
import stat
from pathlib import Path
from .production import IntegratedEnergyService
from .trust import AdmissionDenied

class DurableEnergyService(IntegratedEnergyService):
    """UID-bound durable, at-most-once recovery authorization for cooperative callers.

    Permit consumption commits BEFORE recovery verification. A crash can consume a
    permit without performing recovery (safe denial, no automatic retry).
    """
    def __init__(self, admission, path, allowed_uids, permit_db):
        super().__init__(admission, path, allowed_uids)
        self.permit_db = Path(permit_db)
        if self.permit_db.is_symlink():
            raise AdmissionDenied('permit database symlink')
        parent = self.permit_db.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid() or parent.st_mode & 0o077:
            raise AdmissionDenied('private permit directory required')
        with self.admission.locked():
            self._open_permits(initialize=True).close()

    def _open_permits(self, initialize=False):
        if self.permit_db.is_symlink():
            raise AdmissionDenied('permit database symlink')
        if self.permit_db.exists():
            st = self.permit_db.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1 or st.st_mode & 0o077:
                raise AdmissionDenied('unsafe permit database')
        elif not initialize:
            raise AdmissionDenied('permit database missing')
        db = sqlite3.connect(str(self.permit_db), timeout=5, isolation_level=None)
        try:
            if initialize:
                os.chmod(self.permit_db, 0o600)
                db.execute('PRAGMA journal_mode=DELETE')
                db.execute('PRAGMA synchronous=FULL')
                db.execute('CREATE TABLE IF NOT EXISTS permits (token TEXT PRIMARY KEY, uid INTEGER NOT NULL, sequence INTEGER NOT NULL, digest TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0 CHECK(consumed IN (0,1)))')
            else:
                if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise AdmissionDenied('permit database corrupt')
                if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='permits'").fetchone():
                    raise AdmissionDenied('permit schema missing')
            return db
        except BaseException:
            db.close()
            raise

    def issue(self, uid):
        self._check_pid()
        if type(uid) is not int or uid not in self.allowed_uids:
            raise AdmissionDenied('UID denied')
        with self._mutex, self.admission.locked():
            seq, digest, _ = self.admission.gateway.snapshot()
            from .recovery_broker import BrokerPermit
            permit = BrokerPermit(secrets.token_hex(32), uid, seq, digest)
            with closing(self._open_permits()) as db, db:
                db.execute('INSERT INTO permits(token,uid,sequence,digest) VALUES(?,?,?,?)', (permit.token,uid,seq,digest))
            return permit

    def recover(self, uid, token):
        self._check_pid()
        if type(uid) is not int or uid not in self.allowed_uids or type(token) is not str:
            raise AdmissionDenied('UID or token denied')
        with self._mutex, self.admission.locked():
            db = self._open_permits()
            try:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT uid,sequence,digest,consumed FROM permits WHERE token=?',(token,)).fetchone()
                if row is None or row[0] != uid or row[3]:
                    raise AdmissionDenied('missing, consumed or foreign permit')
                db.execute('UPDATE permits SET consumed=1 WHERE token=? AND uid=? AND consumed=0',(token,uid))
                if db.execute('SELECT changes()').fetchone()[0] != 1:
                    raise AdmissionDenied('permit already consumed')
                if os.environ.get('ENERGY_TEST_CRASH_POINT') == 'permit_before_commit':
                    os._exit(77)  # test-only subprocess injection
                db.commit()
                if os.environ.get('ENERGY_TEST_CRASH_POINT') == 'permit_after_commit':
                    os._exit(78)  # test-only subprocess injection  # durable consume before any recovery side effects
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()
            seq, digest, _ = self.admission.gateway.snapshot()
            if (seq,digest) != (row[1],row[2]):
                raise AdmissionDenied('recovery head changed')
            return seq,digest
