"""TrainOS command-admission requirements; no equipment or network controls."""
from copy import deepcopy
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from snowpiercer_logistics.core import (
    LogisticsLedger, Principal, Location, AuthorizationError, ConflictError,
)
from snowpiercer_logistics.secure import AdmissionError
from snowpiercer_logistics.stage021 import (
    TimedLogisticsLedger, MAX_TTL_MS, production_admission,
)


ADMIN = Principal('trainos-local-host', 'admin')
AUDITOR = Principal('trainos-local-host', 'auditor')


def envelope(key='command-1', revision=0, action='add_location', args=None, **updates):
    result = {'schema_version': 1, 'command_id': key, 'issued_at_ms': 1000,
              'ttl_ms': 1000, 'expected_events': revision, 'action': action,
              'args': args if args is not None else {'location_id': 'a', 'kind': 'warehouse'}}
    result.update(updates)
    return result


@pytest.fixture
def ledger(tmp_path):
    with TimedLogisticsLedger(tmp_path/'ledger.sqlite', clock_ms=lambda: 1100) as db:
        yield db


def receipt_count(db):
    return db._db.execute('SELECT COUNT(*) FROM integration_commands').fetchone()[0]


def test_accepted_envelope_executes_actual_cargo_lifecycle(ledger):
    operations = [
        ('add_container', {'container_id': 'box', 'capacity_kg': 100}),
        ('add_location', {'location_id': 'a', 'kind': 'warehouse'}),
        ('add_location', {'location_id': 'b', 'kind': 'warehouse'}),
        ('register_cargo', {'cargo_id': 'cargo', 'container_id': 'box', 'location_id': 'a'}),
        ('transition_cargo', {'cargo_id': 'cargo', 'target': 'STORED'}),
        ('transition_cargo', {'cargo_id': 'cargo', 'target': 'IN_TRANSIT'}),
        ('record_transfer', {'transfer_id': 'delivery', 'cargo_id': 'cargo', 'source': 'a', 'destination': 'b'}),
    ]
    for revision, (action, args) in enumerate(operations):
        ledger.execute_envelope(ADMIN, envelope(str(revision), revision, action, args))
    assert ledger.get_cargo(AUDITOR, 'cargo').location_id == 'b'
    assert ledger.verify(AUDITOR)['events'] == 7
    assert receipt_count(ledger) == 7


def test_exact_replay_returns_cached_result_after_revision_advanced(ledger):
    request = envelope()
    first = ledger.execute_envelope(ADMIN, request)
    ledger.execute_envelope(ADMIN, envelope('second', 1, args={'location_id': 'b', 'kind': 'warehouse'}))
    assert ledger.execute_envelope(ADMIN, request) == first
    assert ledger.verify(AUDITOR)['events'] == 2
    assert receipt_count(ledger) == 2


@pytest.mark.parametrize('change', [
    {'ttl_ms': 2000}, {'expected_events': 1},
    {'args': {'location_id': 'different', 'kind': 'warehouse'}},
])
def test_reused_identifier_with_changed_envelope_rejected_without_mutation(ledger, change):
    ledger.execute_envelope(ADMIN, envelope())
    with pytest.raises(ConflictError):
        ledger.execute_envelope(ADMIN, envelope(**change))
    assert ledger.verify(AUDITOR)['events'] == 1
    assert receipt_count(ledger) == 1


def test_same_identifier_from_different_principal_rejected(ledger):
    ledger.execute_envelope(ADMIN, envelope())
    with pytest.raises(ConflictError):
        ledger.execute_envelope(Principal('different-host', 'admin'), envelope())
    assert ledger.verify(AUDITOR)['events'] == 1


def test_revoked_role_cannot_replay_committed_result(ledger):
    ledger.execute_envelope(ADMIN, envelope())
    with pytest.raises(AuthorizationError):
        ledger.execute_envelope(AUDITOR, envelope())
    assert ledger.verify(AUDITOR)['events'] == 1


def test_stale_revision_does_not_record_a_receipt(ledger):
    with pytest.raises(ConflictError, match='stale'):
        ledger.execute_envelope(ADMIN, envelope(revision=1))
    assert ledger.verify(AUDITOR)['events'] == 0
    assert receipt_count(ledger) == 0


@pytest.mark.parametrize('changes', [
    {'issued_at_ms': 100, 'ttl_ms': 1000},
    {'issued_at_ms': 1101},
])
def test_expired_or_future_envelopes_rejected(ledger, changes):
    with pytest.raises(AdmissionError):
        ledger.execute_envelope(ADMIN, envelope(**changes))
    assert ledger.verify(AUDITOR)['events'] == 0
    assert receipt_count(ledger) == 0


def test_expiry_rechecked_after_transaction_lock_acquisition(tmp_path):
    times = iter([1000, 1400])
    with TimedLogisticsLedger(tmp_path/'clock.sqlite', clock_ms=lambda: next(times)) as db:
        with pytest.raises(AdmissionError, match='expired'):
            db.execute_envelope(ADMIN, envelope(ttl_ms=300))
        assert db.verify(AUDITOR)['events'] == 0
        assert receipt_count(db) == 0


def test_expired_replay_is_not_admitted(tmp_path):
    now = [1100]
    with TimedLogisticsLedger(tmp_path/'replay.sqlite', clock_ms=lambda: now[0]) as db:
        db.execute_envelope(ADMIN, envelope())
        now[0] = 2000
        with pytest.raises(AdmissionError, match='expired'):
            db.execute_envelope(ADMIN, envelope())
        assert db.verify(AUDITOR)['events'] == 1


def test_failed_mutation_rolls_back_receipt_and_allows_valid_retry(ledger):
    invalid = envelope(action='register_cargo', args={
        'cargo_id': 'unknown', 'container_id': 'missing', 'location_id': 'missing'})
    with pytest.raises(sqlite3.IntegrityError):
        ledger.execute_envelope(ADMIN, invalid)
    assert receipt_count(ledger) == 0
    assert ledger.execute_envelope(ADMIN, envelope()) == {'location_id': 'a'}
    assert ledger.verify(AUDITOR)['events'] == 1


def test_direct_write_cannot_bypass_opt_in_envelope_policy(ledger):
    with pytest.raises(AdmissionError, match='require a validated envelope'):
        ledger.add_location(ADMIN, 'direct', Location('a', 'warehouse'))
    assert ledger.verify(AUDITOR)['events'] == 0


def test_legacy_command_key_is_not_silently_imported(tmp_path):
    path = tmp_path/'legacy.sqlite'
    with LogisticsLedger(path) as old:
        old.add_location(ADMIN, 'command-1', Location('a', 'warehouse'))
    with TimedLogisticsLedger(path, clock_ms=lambda: 1100) as db:
        with pytest.raises(ConflictError, match='legacy'):
            db.execute_envelope(ADMIN, envelope())
        assert receipt_count(db) == 0


def test_receipt_and_idempotency_survive_reopen(tmp_path):
    path = tmp_path/'reopen.sqlite'
    with TimedLogisticsLedger(path, clock_ms=lambda: 1100) as db:
        original = db.execute_envelope(ADMIN, envelope())
    with TimedLogisticsLedger(path, clock_ms=lambda: 1200) as db:
        assert db.execute_envelope(ADMIN, envelope()) == original
        assert db.verify(AUDITOR)['events'] == 1
        assert receipt_count(db) == 1


def test_independent_connections_compare_revision_atomically(tmp_path):
    path = tmp_path/'concurrent.sqlite'
    barrier = Barrier(2)
    with TimedLogisticsLedger(path, clock_ms=lambda: 1100) as a, \
         TimedLogisticsLedger(path, clock_ms=lambda: 1100) as b:
        def run(db, number):
            barrier.wait(timeout=5)
            try:
                db.execute_envelope(ADMIN, envelope('key-'+str(number), args={
                    'location_id': 'location-'+str(number), 'kind': 'warehouse'}))
                return 'accepted'
            except ConflictError:
                return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, a, 1)
            second = pool.submit(run, b, 2)
            assert sorted([first.result(timeout=10), second.result(timeout=10)]) == ['accepted', 'stale']
        assert a.verify(AUDITOR)['events'] == 1
        assert receipt_count(a) == 1


def test_concurrent_duplicate_across_connections_has_single_effect(tmp_path):
    path = tmp_path/'duplicate.sqlite'
    barrier = Barrier(2)
    with TimedLogisticsLedger(path, clock_ms=lambda: 1100) as a, \
         TimedLogisticsLedger(path, clock_ms=lambda: 1100) as b:
        def run(db):
            barrier.wait(timeout=5)
            return db.execute_envelope(ADMIN, envelope())
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(run, a), pool.submit(run, b)
            assert first.result(timeout=10) == second.result(timeout=10) == {'location_id': 'a'}
        assert a.verify(AUDITOR)['events'] == 1
        assert receipt_count(a) == 1


@pytest.mark.parametrize('field,value', [
    ('schema_version', True), ('schema_version', 2),
    ('issued_at_ms', True), ('issued_at_ms', -1),
    ('ttl_ms', True), ('ttl_ms', 0), ('ttl_ms', MAX_TTL_MS+1),
    ('expected_events', False), ('expected_events', -1),
    ('command_id', ''), ('action', 'recover'), ('action', ['add_location']),
    ('args', {'location_id': 'a', 'kind': 'warehouse', 'principal': 'admin'}),
])
def test_malformed_or_unsupported_envelope_rejected_without_effect(ledger, field, value):
    request = envelope()
    request[field] = deepcopy(value)
    with pytest.raises(AdmissionError):
        ledger.execute_envelope(ADMIN, request)
    assert ledger.verify(AUDITOR)['events'] == 0
    assert receipt_count(ledger) == 0


def test_client_identity_field_rejected(ledger):
    with pytest.raises(AdmissionError):
        ledger.execute_envelope(ADMIN, envelope(principal_id='forged-client'))


def test_production_admission_remains_closed():
    with pytest.raises(AdmissionError, match='NO-GO'):
        production_admission()
