"""SQLite-local recovery fencing for an OFFLINE logical lifecycle prototype.

All cooperating writers must use this API. Legacy PersistentLifecycle is NOT fenced.
"""
from __future__ import annotations
import json
import sqlite3
import time
from dataclasses import dataclass
from .persistence import PersistentLifecycle, RecoveryError, fingerprint

class FencingError(RecoveryError):
    pass

@dataclass(frozen=True)
class FenceToken:
    owner: str
    epoch: int
    expires_at_ns: int

class FencedLifecycle(PersistentLifecycle):
    """Epoch fencing + expiry enforced inside the same SQLite write transaction.

    No distributed consensus, no external equipment control, no real-time guarantee.
    """
    def __init__(self, registry, path, *, clock_ns=None):
        self._clock = clock_ns or time.time_ns
        super().__init__(registry, path)
        self.db.execute('''CREATE TABLE IF NOT EXISTS coordination (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            epoch INTEGER NOT NULL CHECK(epoch>=0),
            owner TEXT NOT NULL, expires_at_ns INTEGER NOT NULL,
            registry_fingerprint TEXT NOT NULL)''')
        self._token = None

    def _now(self):
        value = self._clock()
        if type(value) is not int or value < 0:
            raise FencingError('invalid clock')
        return value

    def _begin(self):
        self.db.execute('BEGIN IMMEDIATE')

    def _rollback(self):
        if self.db.in_transaction:
            self.db.execute('ROLLBACK')

    def _row(self):
        return self.db.execute('SELECT epoch,owner,expires_at_ns,registry_fingerprint FROM coordination WHERE singleton=1').fetchone()

    def acquire(self, owner: str, *, ttl_ns: int) -> FenceToken:
        if not isinstance(owner, str) or not owner.strip() or len(owner)>128 or type(ttl_ns) is not int or ttl_ns <= 0:
            raise FencingError('invalid owner or ttl')
        self._begin()
        try:
            now = self._now()
            row = self._row()
            if row and row[3] != fingerprint(self.registry):
                raise FencingError('registry mismatch')
            if row and row[2] > now:
                raise FencingError('lease already held; wait for expiry or release')
            epoch = row[0]+1 if row else 1
            expiry = now + ttl_ns
            if expiry > 2**63-1:
                raise FencingError('lease overflow')
            self._replay()  # refuse corrupt history before issuing a token
            self.db.execute('INSERT INTO coordination VALUES(1,?,?,?,?) ON CONFLICT(singleton) DO UPDATE SET epoch=excluded.epoch,owner=excluded.owner,expires_at_ns=excluded.expires_at_ns,registry_fingerprint=excluded.registry_fingerprint', (epoch,owner,expiry,fingerprint(self.registry)))
            self.db.execute('COMMIT')
        except Exception:
            self._rollback()
            raise
        self._token = FenceToken(owner,epoch,expiry)
        return self._token

    def _check(self, token, now):
        if not isinstance(token,FenceToken):
            raise FencingError('fence token required')
        row=self._row()
        if not row or (row[0],row[1],row[2]) != (token.epoch,token.owner,token.expires_at_ns) or row[3]!=fingerprint(self.registry):
            raise FencingError('stale or revoked fence')
        if now >= row[2]:
            raise FencingError('lease expired')

    def renew(self, token: FenceToken, *, ttl_ns: int) -> FenceToken:
        if type(ttl_ns) is not int or ttl_ns<=0:
            raise FencingError('invalid ttl')
        now=self._now()
        self._begin()
        try:
            self._check(token,now)
            expiry=now+ttl_ns
            if expiry>2**63-1:
                raise FencingError('lease overflow')
            self.db.execute('UPDATE coordination SET expires_at_ns=? WHERE singleton=1',(expiry,))
            self.db.execute('COMMIT')
        except Exception:
            self._rollback()
            raise
        self._token=FenceToken(token.owner,token.epoch,expiry)
        return self._token

    def release(self, token: FenceToken):
        now=self._now()
        self._begin()
        try:
            self._check(token,now)
            self.db.execute('UPDATE coordination SET expires_at_ns=0 WHERE singleton=1')
            self.db.execute('COMMIT')
        except Exception:
            self._rollback()
            raise
        self._token=None

    def transition(self, component_id, next_state, *, event_id, reason, actor, timestamp_utc=None, token=None):
        now=self._now()
        self._begin()
        try:
            self._check(token,now)
            fresh=self._replay()
            event=fresh.transition(component_id,next_state,event_id=event_id,reason=reason,actor=actor,timestamp_utc=timestamp_utc)
            self.db.execute('INSERT INTO events(sequence,event_id,payload) VALUES(?,?,?)',(event.sequence,event.event_id,json.dumps(event.as_dict(),sort_keys=True,separators=(',',':'),ensure_ascii=False)))
            # Reject a lease that expires during a potentially slow replay/transition.
            self._check(token,self._now())
            self.db.execute('COMMIT')
        except Exception:
            self._rollback()
            raise
        self.lifecycle=fresh
        return event

    def recover(self, *, token=None):
        now=self._now()
        self._begin()
        try:
            self._check(token,now)
            fresh=self._replay()
            self._check(token,self._now())
            self.db.execute('COMMIT')
        except Exception:
            self._rollback()
            raise
        self.lifecycle=fresh
        return fresh
