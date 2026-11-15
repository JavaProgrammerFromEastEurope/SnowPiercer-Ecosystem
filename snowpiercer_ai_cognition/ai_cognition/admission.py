"""AI-CORE-002 authenticated, bounded, replay-resistant admission (Python 3.9+)."""
import hashlib
import hmac
import json
import math
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Mapping, Any

from .core import Observation, assess

MAX_WIRE_BYTES = 8192
MAX_AGE_SECONDS = 300
MAX_FUTURE_SECONDS = 30

class AdmissionRejected(ValueError):
    """Fail-closed rejection; message is a stable non-sensitive reason code."""


def _json_bytes(obj):
    try:
        return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, OverflowError) as exc:
        raise AdmissionRejected('INVALID_ENVELOPE') from exc


def _valid_time(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 253402300799


def signed_envelope(observation: Mapping[str, Any], timestamp: int, nonce: str, key: bytes):
    """Producer helper. Secrets must be provisioned out-of-band."""
    Observation.parse(observation)
    if not _valid_time(timestamp) or not _valid_nonce(nonce):
        raise ValueError('invalid timestamp or nonce')
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError('key must contain at least 32 bytes')
    fields = {'observation': dict(observation), 'timestamp': timestamp, 'nonce': nonce}
    raw = _json_bytes(fields)
    if len(raw) > MAX_WIRE_BYTES:
        raise ValueError('oversized envelope')
    fields['mac'] = hmac.new(key, raw, hashlib.sha256).hexdigest()
    if len(_json_bytes(fields)) > MAX_WIRE_BYTES:
        raise ValueError('oversized envelope')
    return fields


def _valid_nonce(value):
    return (isinstance(value, str) and 16 <= len(value) <= 128 and value.isascii()
            and all(c.isalnum() or c in '-_.' for c in value))


class ReplayStore:
    """Atomic SQLite replay reservation, persisted across restarts; fail closed on I/O errors."""
    def __init__(self, path: str):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, timeout=5, check_same_thread=False, isolation_level=None)
        try:
            self._db.execute('PRAGMA busy_timeout=5000')
            self._db.execute('PRAGMA synchronous=FULL')
            self._db.execute('CREATE TABLE IF NOT EXISTS seen (source TEXT NOT NULL, nonce TEXT NOT NULL, event_id TEXT NOT NULL, admitted_at INTEGER NOT NULL, PRIMARY KEY(source, nonce), UNIQUE(source, event_id))')
        except Exception:
            self._db.close()
            raise

    def reserve(self, source: str, nonce: str, event_id: str, now: int):
        with self._lock:
            try:
                self._db.execute('BEGIN IMMEDIATE')
                # Fence all legacy writes, including cross-process connections.
                if self._db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rotation'").fetchone():
                    if self._db.execute("SELECT 1 FROM rotation WHERE phase != 'ACTIVE' LIMIT 1").fetchone():
                        raise AdmissionRejected('ROTATION_INCOMPLETE')
                    meta = self._db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lifecycle_anchor'").fetchone()
                    if meta:
                        pathrow = self._db.execute('SELECT path FROM lifecycle_anchor WHERE id=1').fetchone()
                        if not pathrow:
                            raise AdmissionRejected('ANCHOR_UNAVAILABLE')
                        try:
                            with open(pathrow[0], 'r', encoding='ascii') as f:
                                raw = f.read(24)
                            anchor = int(raw.strip()) if raw.endswith('\n') and raw[:-1].isdigit() else -1
                        except (OSError, ValueError):
                            raise AdmissionRejected('ANCHOR_UNAVAILABLE')
                        epoch = self._db.execute('SELECT epoch FROM lifecycle_meta WHERE id=1').fetchone()[0]
                        if epoch != anchor:
                            raise AdmissionRejected('EPOCH_MISMATCH')
                self._db.execute('INSERT INTO seen VALUES (?, ?, ?, ?)', (source, nonce, event_id, now))
                self._db.execute('COMMIT')
            except BaseException as exc:
                try:
                    self._db.execute('ROLLBACK')
                except sqlite3.Error:
                    pass
                if isinstance(exc, sqlite3.IntegrityError):
                    raise AdmissionRejected('REPLAY_DETECTED') from exc
                if isinstance(exc, sqlite3.Error):
                    raise AdmissionRejected('REPLAY_STORE_UNAVAILABLE') from exc
                raise

    def close(self):
        with self._lock:
            self._db.close()


class TrustedAdmission:
    """Authenticated admission boundary. Keys map source -> independent secret bytes."""
    def __init__(self, keys: Mapping[str, bytes], replay_store: ReplayStore, *, max_age=MAX_AGE_SECONDS,
                 max_future=MAX_FUTURE_SECONDS, clock=None):
        if not isinstance(keys, Mapping) or not keys or any(
            not isinstance(k, str) or not isinstance(v, bytes) or len(v) < 32 for k, v in keys.items()
        ):
            raise ValueError('invalid key registry')
        if not isinstance(replay_store, ReplayStore):
            raise ValueError('replay_store required')
        if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 0:
            raise ValueError('invalid max_age')
        if not isinstance(max_future, int) or isinstance(max_future, bool) or max_future < 0:
            raise ValueError('invalid max_future')
        self._keys = dict(keys)
        self._store = replay_store
        self._max_age = max_age
        self._max_future = max_future
        self._clock = clock if clock is not None else time.time

    def admit(self, envelope: Mapping[str, Any]):
        if not isinstance(envelope, Mapping):
            raise AdmissionRejected('INVALID_ENVELOPE')
        # Size limit precedes signature verification and replay-store writes.
        raw = _json_bytes(envelope)
        if len(raw) > MAX_WIRE_BYTES:
            raise AdmissionRejected('OVERSIZED_ENVELOPE')
        if set(envelope) != {'observation', 'timestamp', 'nonce', 'mac'}:
            raise AdmissionRejected('INVALID_ENVELOPE')
        observation = envelope['observation']
        try:
            parsed = Observation.parse(observation)
        except (ValueError, TypeError, KeyError) as exc:
            raise AdmissionRejected('INVALID_OBSERVATION') from exc
        timestamp, nonce, mac = envelope['timestamp'], envelope['nonce'], envelope['mac']
        if not _valid_time(timestamp) or not _valid_nonce(nonce) or not isinstance(mac, str) or len(mac) != 64 or not mac.isascii() or any(c not in '0123456789abcdef' for c in mac):
            raise AdmissionRejected('INVALID_ENVELOPE')
        key = self._keys.get(parsed.source)
        if key is None:
            raise AdmissionRejected('UNTRUSTED_SOURCE')
        body = {'observation': dict(observation), 'timestamp': timestamp, 'nonce': nonce}
        expected = hmac.new(key, _json_bytes(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise AdmissionRejected('AUTHENTICATION_FAILED')
        now_value = self._clock()
        if not isinstance(now_value, (int, float)) or not math.isfinite(now_value) or now_value < 0:
            raise AdmissionRejected('CLOCK_UNAVAILABLE')
        now = int(now_value)
        if timestamp < now - self._max_age:
            raise AdmissionRejected('STALE_OBSERVATION')
        if timestamp > now + self._max_future:
            raise AdmissionRejected('FUTURE_OBSERVATION')
        # Legacy TrustedAdmission cannot use a retired key once lifecycle exists.
        # The check is repeated under the SQLite reservation lock below to avoid TOCTOU.
        with self._store._lock:
            try:
                row = self._store._db.execute("SELECT generation, fingerprint, phase FROM rotation WHERE source=?", (parsed.source,)).fetchone()
            except sqlite3.Error as exc:
                if 'no such table' not in str(exc):
                    raise AdmissionRejected('REPLAY_STORE_UNAVAILABLE') from exc
                row = None
            if row is not None:
                fingerprint = hmac.new(key, (parsed.source + ':' + str(row[0])).encode(), hashlib.sha256).hexdigest()
                if row[2] != 'ACTIVE' or not hmac.compare_digest(fingerprint, row[1]):
                    raise AdmissionRejected('LEGACY_KEY_RETIRED_OR_FENCED')
        # Replay reservation is committed before any recommendation is released.
        self._store.reserve(parsed.source, nonce, parsed.event_id, now)
        return assess(dict(observation))
