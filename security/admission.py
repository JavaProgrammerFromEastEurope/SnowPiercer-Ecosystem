"""Reference implementation of SP-IC-004. SIMULATION ONLY, not an OS security boundary.

No code path here mints an operational authorization, controls hardware or attests
an OS identity. Production is unconditionally blocked until independent evidence
exists for OS MAC, cross-UID authentication, durable witness, and service lifecycle.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any


class RequestRejected(ValueError):
    """Malformed input never reaches policy evaluation."""


class AdmissionUnavailable(RuntimeError):
    """No decision can be used when an audit or admission boundary fails."""


class ProductionBlocked(PermissionError):
    """Independent production controls have not been demonstrated."""


ACTIONS = frozenset({'read', 'observe', 'simulate', 'issue', 'recover',
                     'override', 'actuate', 'configure', 'admin'})
PRIVILEGED = frozenset({'issue', 'recover', 'override', 'actuate', 'configure', 'admin'})
LABEL = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,127}$')
CORRELATION = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$')
REQUIRED = frozenset({'request_id', 'principal_id', 'resource', 'action',
                      'policy_version', 'correlation_id'})
GENESIS = '0' * 64


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      allow_nan=False, separators=(',', ':')).encode('utf-8')


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise RequestRejected('DUPLICATE_JSON_KEY')
        output[key] = value
    return output


def parse_request_json(raw: bytes) -> dict:
    """Decode one size-bounded object with duplicate-key rejection."""
    if not isinstance(raw, bytes) or not raw or len(raw) > 4096:
        raise RequestRejected('INVALID_FRAME_SIZE')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_reject_duplicates,
                           parse_constant=lambda _: (_ for _ in ()).throw(RequestRejected('INVALID_NUMBER')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise RequestRejected('INVALID_JSON') from exc
    return validate_request(value)


def validate_request(value: Any) -> dict:
    if not isinstance(value, dict) or set(value) != REQUIRED:
        raise RequestRejected('INVALID_REQUEST_FIELDS')
    if any(not isinstance(value[k], str) for k in REQUIRED):
        raise RequestRejected('INVALID_REQUEST_TYPE')
    try:
        parsed = uuid.UUID(value['request_id'])
    except (ValueError, AttributeError) as exc:
        raise RequestRejected('INVALID_REQUEST_ID') from exc
    if parsed.version != 4 or str(parsed) != value['request_id']:
        raise RequestRejected('INVALID_REQUEST_ID')
    for key in ('principal_id', 'resource', 'policy_version'):
        if not LABEL.fullmatch(value[key]):
            raise RequestRejected('INVALID_LABEL')
    if not CORRELATION.fullmatch(value['correlation_id']):
        raise RequestRejected('INVALID_CORRELATION_ID')
    if value['action'] not in ACTIONS:
        raise RequestRejected('UNREGISTERED_ACTION')
    return value.copy()


class LocalSimulation:
    """Local test-only evaluation with an HMAC hash-chain audit.

    WARNING: local HMAC and SQLite cannot protect against same-UID key theft,
    complete database rollback, a hostile operating system, or impersonation.
    """

    def __init__(self, db: Path | str, key: bytes, *, policy_version: str = 'SEC-POLICY-0.1'):
        self.db = Path(db)
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError('At least 32 random bytes of test-only audit key are required')
        self._key = key
        self._policy_version = policy_version
        self._thread_lock = threading.RLock()
        self._last_tip: str | None = None
        if policy_version != 'SEC-POLICY-0.1':
            raise ValueError('Unknown simulation policy')
        if not self.db.parent.is_dir():
            raise ValueError('State directory must already exist')
        self._initialize()

    @staticmethod
    def require_production_admission() -> None:
        """No environment variable or test flag can override this boundary."""
        raise ProductionBlocked('NO_GO: independent OS-MAC, trusted UID broker, '
                                'anti-rollback witness and lifecycle evidence absent')

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db), timeout=2.0, isolation_level=None)
        try:
            con.execute('PRAGMA busy_timeout=2000')
            con.execute('PRAGMA trusted_schema=OFF')
            con.execute('PRAGMA synchronous=FULL')
            con.execute('PRAGMA foreign_keys=ON')
            return con
        except BaseException:
            con.close()
            raise

    def _initialize(self) -> None:
        try:
            con = self._connect()
            try:
                con.execute('PRAGMA journal_mode=WAL')
                con.execute('BEGIN IMMEDIATE')
                con.execute('CREATE TABLE IF NOT EXISTS audit_events('
                            'seq INTEGER PRIMARY KEY AUTOINCREMENT, '
                            'request_id TEXT NOT NULL UNIQUE, '
                            'payload BLOB NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL)')
                con.execute('CREATE TABLE IF NOT EXISTS metadata(name TEXT PRIMARY KEY, value TEXT NOT NULL)')
                key_id = hashlib.sha256(self._key).hexdigest()
                found = con.execute("SELECT value FROM metadata WHERE name='key_id'").fetchone()
                if found is None:
                    con.execute('INSERT INTO metadata(name, value) VALUES (?, ?)', ('key_id', key_id))
                elif not hmac.compare_digest(found[0], key_id):
                    raise AdmissionUnavailable('AUDIT_KEY_MISMATCH')
                con.execute('COMMIT')
            except BaseException:
                if con.in_transaction:
                    con.execute('ROLLBACK')
                raise
            finally:
                con.close()
        except sqlite3.Error as exc:
            raise AdmissionUnavailable('AUDIT_INIT_FAILED') from exc

    def _verify(self, con: sqlite3.Connection) -> str:
        found = con.execute("SELECT value FROM metadata WHERE name='key_id'").fetchone()
        if found is None or not hmac.compare_digest(found[0], hashlib.sha256(self._key).hexdigest()):
            raise AdmissionUnavailable('AUDIT_KEY_MISMATCH')
        previous = GENESIS
        rows = con.execute('SELECT seq, payload, previous, digest FROM audit_events ORDER BY seq').fetchall()
        expected_seq = 1
        for seq, payload, stored_previous, digest in rows:
            if seq != expected_seq or not isinstance(payload, bytes) or stored_previous != previous:
                raise AdmissionUnavailable('AUDIT_CHAIN_BROKEN')
            expected = hmac.new(self._key, previous.encode('ascii') + b'\x00' + payload,
                                hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, digest):
                raise AdmissionUnavailable('AUDIT_SIGNATURE_INVALID')
            previous = digest
            expected_seq += 1
        if self._last_tip is not None and not hmac.compare_digest(self._last_tip, previous):
            raise AdmissionUnavailable('IN_PROCESS_AUDIT_ROLLBACK')
        return previous

    def audit_tip(self) -> str:
        """Check the local chain; NOT an independently protected root."""
        with self._thread_lock:
            try:
                con = self._connect()
                try:
                    con.execute('BEGIN')
                    tip = self._verify(con)
                    con.execute('COMMIT')
                    return tip
                finally:
                    con.close()
            except sqlite3.Error as exc:
                raise AdmissionUnavailable('AUDIT_READ_FAILED') from exc

    def admit(self, request: dict, *, simulated_broker_principal: str) -> dict:
        """Record and return a NON-EXECUTABLE simulation decision.

        simulated_broker_principal does not attest a real OS identity.
        A returned ALLOW must never be used for actuation or live operations.
        """
        req = validate_request(request)
        if not isinstance(simulated_broker_principal, str) or not LABEL.fullmatch(simulated_broker_principal):
            raise RequestRejected('INVALID_SIMULATED_PRINCIPAL')
        if req['policy_version'] != self._policy_version:
            raise RequestRejected('POLICY_VERSION_MISMATCH')
        if req['principal_id'] != simulated_broker_principal:
            decision, reason = 'DENY', 'IDENTITY_MISMATCH'
        elif req['action'] in PRIVILEGED:
            decision, reason = 'DENY', 'PRIVILEGED_ACTION_UNAVAILABLE'
        elif ((req['principal_id'], req['resource'], req['action']) in {
                ('trainos-observer', 'trainos.telemetry', 'read'),
                ('security-auditor', 'security.audit', 'read'),
                ('energy-simulator', 'energy.scenario', 'simulate'),
            }):
            decision, reason = 'ALLOW', 'SIMULATION_POLICY_MATCH'
        else:
            decision, reason = 'DENY', 'DEFAULT_DENY'
        recorded = {'request': req, 'decision': decision, 'reason': reason,
                    'authority': 'SIMULATION_ONLY', 'executable': False,
                    'operationalReady': False}
        payload = _canonical(recorded)
        with self._thread_lock:
            try:
                con = self._connect()
                try:
                    con.execute('BEGIN IMMEDIATE')
                    previous = self._verify(con)
                    digest = hmac.new(self._key, previous.encode('ascii') + b'\x00' + payload,
                                      hashlib.sha256).hexdigest()
                    con.execute('INSERT INTO audit_events(request_id, payload, previous, digest) '
                                'VALUES (?, ?, ?, ?)', (req['request_id'], payload, previous, digest))
                    con.execute('COMMIT')
                    self._last_tip = digest
                except BaseException:
                    if con.in_transaction:
                        con.execute('ROLLBACK')
                    raise
                finally:
                    con.close()
            except sqlite3.IntegrityError as exc:
                # A trigger failure or another integrity error is not a nonce replay.
                if getattr(exc, 'sqlite_errorname', '') == 'SQLITE_CONSTRAINT_UNIQUE':
                    raise AdmissionUnavailable('REPLAY_DETECTED') from exc
                raise AdmissionUnavailable('AUDIT_WRITE_FAILED') from exc
            except sqlite3.Error as exc:
                raise AdmissionUnavailable('AUDIT_WRITE_FAILED') from exc
        return {'request_id': req['request_id'], 'principal_id': req['principal_id'],
                'resource': req['resource'], 'action': req['action'],
                'correlation_id': req['correlation_id'], 'policy_version': self._policy_version,
                'decision': decision, 'reason': reason, 'audit_ref': 'security-sim://audit/' + digest,
                'authority': 'SIMULATION_ONLY', 'executable': False, 'operationalReady': False}
