"""Offline durable lifecycle journal. No physical control; single-writer SQLite."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from hashlib import sha256
from .lifecycle import Lifecycle, State, TransitionError

class RecoveryError(RuntimeError):
    pass

def fingerprint(registry):
    payload = {'version': registry.version, 'components': registry.components, 'requirements': registry.requirements}
    return sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

class PersistentLifecycle:
    """SQLite transactions commit before publishing a transition; replay all events on startup."""
    def __init__(self, registry, path):
        self.registry = registry
        self.path = Path(path)
        self.db = sqlite3.connect(str(self.path), isolation_level=None, timeout=5)
        try:
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL)')
            self.db.execute('BEGIN IMMEDIATE')
            current = self.db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
            fp = fingerprint(registry)
            if current is None:
                if self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]:
                    raise RecoveryError('unbound journal contains events')
                self.db.execute("INSERT INTO metadata VALUES ('fingerprint', ?)", (fp,))
            elif current[0] != fp:
                raise RecoveryError('registry fingerprint mismatch')
            self.lifecycle = self._replay()
            self.db.execute('COMMIT')
        except Exception:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            self.db.close()
            raise

    def _replay(self):
        lifecycle = Lifecycle(self.registry)
        rows = self.db.execute('SELECT sequence, event_id, payload FROM events ORDER BY sequence').fetchall()
        for sequence, event_id, payload in rows:
            try:
                data = json.loads(payload)
                if not isinstance(data, dict) or set(data) != {'sequence','event_id','component_id','previous_state','next_state','reason','actor','timestamp_utc','previous_hash','event_hash'}:
                    raise ValueError('invalid event fields')
                if sequence != data['sequence'] or event_id != data['event_id']:
                    raise ValueError('event index mismatch')
                event = lifecycle.transition(data['component_id'], data['next_state'], event_id=data['event_id'], reason=data['reason'], actor=data['actor'], timestamp_utc=data['timestamp_utc'])
                if event.as_dict() != data:
                    raise ValueError('event chain or transition mismatch')
            except (ValueError, TypeError, KeyError, TransitionError) as exc:
                raise RecoveryError(f'journal corruption at sequence {sequence}: {exc}') from exc
        if not lifecycle.verify_audit():
            raise RecoveryError('audit verification failed')
        return lifecycle

    def transition(self, component_id, next_state, *, event_id, reason, actor, timestamp_utc=None):
        """Serialize writers; verify committed history; publish state only after COMMIT."""
        self.db.execute('BEGIN IMMEDIATE')
        try:
            fresh = self._replay()
            event = fresh.transition(component_id, next_state, event_id=event_id, reason=reason, actor=actor, timestamp_utc=timestamp_utc)
            self.db.execute('INSERT INTO events(sequence,event_id,payload) VALUES (?,?,?)',
                            (event.sequence, event.event_id, json.dumps(event.as_dict(), sort_keys=True, separators=(',', ':'), ensure_ascii=False)))
            self.db.execute('COMMIT')
        except Exception:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise
        self.lifecycle = fresh
        return event

    def recover(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            recovered = self._replay()
            self.db.execute('COMMIT')
        except Exception:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise
        self.lifecycle = recovered
        return recovered

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
