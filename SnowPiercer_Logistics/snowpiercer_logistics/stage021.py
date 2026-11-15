"""LOG-CORE-021: timed, revision-checked local TrainOS command admission.

This opt-in software adapter does not authenticate remote identities, join the
four-UID witness transaction, or authorize production/physical actuation.
"""
import hashlib
import json
import time

from .core import (LogisticsLedger, Container, Location, Cargo, CargoState,
                   Mission, MissionState, Transfer, ConflictError)
from .secure import AdmissionError


ENVELOPE_FIELDS = frozenset({
    'schema_version', 'command_id', 'issued_at_ms', 'ttl_ms',
    'expected_events', 'action', 'args',
})
MAX_TTL_MS = 86_400_000
MAX_INTEGER = 2**63 - 1
ACTION_FIELDS = {
    'add_container': {'container_id', 'capacity_kg'},
    'add_location': {'location_id', 'kind'},
    'register_cargo': {'cargo_id', 'container_id', 'location_id'},
    'transition_cargo': {'cargo_id', 'target'},
    'create_mission': {'mission_id', 'cargo_id'},
    'transition_mission': {'mission_id', 'target'},
    'record_transfer': {'transfer_id', 'cargo_id', 'source', 'destination'},
}


def validate_command_envelope(envelope):
    """Validate a closed schema and return a detached JSON snapshot.

    Identity/roles are deliberately absent from the wire envelope: the local
    host supplies a separately trusted Principal to execute_envelope().
    """
    if type(envelope) is not dict or set(envelope) != ENVELOPE_FIELDS:
        raise AdmissionError('invalid LOG-CORE-021 envelope fields')
    if type(envelope['schema_version']) is not int or envelope['schema_version'] != 1:
        raise AdmissionError('unsupported command schema version')
    for field in ('issued_at_ms', 'expected_events'):
        value = envelope[field]
        if type(value) is not int or not 0 <= value <= MAX_INTEGER:
            raise AdmissionError('invalid ' + field)
    if type(envelope['ttl_ms']) is not int or not 0 < envelope['ttl_ms'] <= MAX_TTL_MS:
        raise AdmissionError('invalid command TTL')
    try:
        LogisticsLedger._required(envelope['command_id'])
    except ValueError as exc:
        raise AdmissionError('invalid command identifier') from exc
    action = envelope['action']
    if type(action) is not str or action not in ACTION_FIELDS:
        raise AdmissionError('unsupported integration action')
    args = envelope['args']
    if type(args) is not dict or set(args) != ACTION_FIELDS[action]:
        raise AdmissionError('invalid integration action arguments')
    for name, value in args.items():
        if name == 'capacity_kg':
            if type(value) is not int or not 0 < value <= MAX_INTEGER:
                raise AdmissionError('invalid container capacity')
        else:
            try:
                LogisticsLedger._required(value)
            except ValueError as exc:
                raise AdmissionError('invalid action argument: ' + name) from exc
    try:
        return json.loads(json.dumps(envelope, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise AdmissionError('envelope is not canonical JSON') from exc


class TimedLogisticsLedger(LogisticsLedger):
    """Opt-in local command API with atomic admission and persistent replay keys.

    Existing ledger commands must enter through execute_envelope on this class.
    Original LogisticsLedger users retain their prior API and semantics.
    The clock and Principal are trusted host dependencies, not client claims.
    """
    def __init__(self, path, *, clock_ms=None):
        super().__init__(path)
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._envelope_context = None
        try:
            self._db.execute('''CREATE TABLE IF NOT EXISTS integration_commands(
                command_id TEXT PRIMARY KEY, envelope_hash TEXT NOT NULL,
                expected_events INTEGER NOT NULL)''')
        except BaseException:
            self.close()
            raise

    def _check_time(self, envelope):
        now = self._clock_ms()
        if type(now) is not int or not 0 <= now <= MAX_INTEGER:
            raise AdmissionError('trusted clock must return integer epoch milliseconds')
        if now < envelope['issued_at_ms']:
            raise AdmissionError('command issued in the future or clock regressed')
        if now >= envelope['issued_at_ms'] + envelope['ttl_ms']:
            raise AdmissionError('command expired')

    def execute_envelope(self, principal, envelope):
        request = validate_command_envelope(envelope)
        permission = 'setup' if request['action'] in ('add_container', 'add_location') else 'write'
        self._authorize(principal, permission)
        self._required(principal.identity)
        self._check_time(request)
        canonical = json.dumps({'principal': principal.identity, 'envelope': request},
                               sort_keys=True, separators=(',', ':'), allow_nan=False)
        context = (request, hashlib.sha256(canonical.encode()).hexdigest())
        with self._lock:
            if self._envelope_context is not None:
                raise AdmissionError('nested integration command forbidden')
            self._envelope_context = context
            try:
                return self._execute_typed(principal, request)
            finally:
                self._envelope_context = None

    def _execute_typed(self, principal, request):
        action, key, args = request['action'], request['command_id'], request['args']
        constructors = {'add_container': Container, 'add_location': Location,
                        'register_cargo': Cargo, 'create_mission': Mission,
                        'record_transfer': Transfer}
        if action in constructors:
            return getattr(self, action)(principal, key, constructors[action](**args))
        if action == 'transition_cargo':
            return self.transition_cargo(principal, key, args['cargo_id'], CargoState(args['target']))
        return self.transition_mission(principal, key, args['mission_id'], MissionState(args['target']))

    def _admit_command(self, db, principal, key, kind, payload):
        if self._envelope_context is None:
            raise AdmissionError('timed ledger writes require a validated envelope')
        request, fingerprint = self._envelope_context
        if request['command_id'] != key:
            raise AdmissionError('command envelope context mismatch')
        # Recheck after BEGIN IMMEDIATE: acquiring the SQLite write lock can
        # consume the remaining TTL. The revision read is in this transaction.
        self._check_time(request)
        receipt = db.execute('SELECT envelope_hash FROM integration_commands WHERE command_id=?',
                             (key,)).fetchone()
        command = db.execute('SELECT fingerprint FROM commands WHERE key=?', (key,)).fetchone()
        if receipt:
            if receipt[0] != fingerprint:
                raise ConflictError('command identifier reused with a different envelope or principal')
            if command is None:
                raise AdmissionError('integration receipt has no committed command')
            return  # Exact replay; the original command returns its cached result.
        if command:
            raise ConflictError('command identifier already belongs to a legacy command')
        revision = db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        if revision != request['expected_events']:
            raise ConflictError('stale logistics revision')
        db.execute('INSERT INTO integration_commands VALUES(?,?,?)',
                   (key, fingerprint, request['expected_events']))


def production_admission(*args, **kwargs):
    raise AdmissionError('LOG-CORE-021 NO-GO: local integration adapter is not production admission')
