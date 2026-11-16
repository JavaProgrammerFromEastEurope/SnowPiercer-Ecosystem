from concurrent.futures import ThreadPoolExecutor

import pytest

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
    IdempotencyStatus,
)


def test_same_key_and_canonical_payload_claims_once_and_survives_restart(tmp_path):
    path = tmp_path / "idempotency.sqlite3"
    store = CommandIdempotencyStore(path)
    first = store.claim("request-1", "move_robot", {"x": 1, "y": 2})
    repeated = store.claim("request-1", "move_robot", {"y": 2, "x": 1})
    assert first.created is True
    assert repeated.created is False
    assert repeated.record.status is IdempotencyStatus.CLAIMED
    store.close()

    reopened = CommandIdempotencyStore(path)
    again = reopened.claim("request-1", "move_robot", {"x": 1, "y": 2})
    assert not again.created
    assert again.record.status is IdempotencyStatus.CLAIMED
    reopened.close()


def test_reusing_key_for_different_command_or_payload_is_rejected(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    store.claim("key", "open_door", {"door": "A"})
    with pytest.raises(IdempotencyConflict, match="different command"):
        store.claim("key", "open_door", {"door": "B"})
    with pytest.raises(IdempotencyConflict, match="different command"):
        store.claim("key", "close_door", {"door": "A"})
    assert store.get("key").status is IdempotencyStatus.CLAIMED
    store.close()


def test_duplicate_completion_is_idempotent_but_conflicting_result_is_rejected(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    store.claim("key", "read_sensor", {"sensor": 7})
    first = store.complete("key", {"value": 42})
    duplicate = store.complete("key", {"value": 42})
    assert first.status is duplicate.status is IdempotencyStatus.COMPLETED
    with pytest.raises(IdempotencyConflict, match="conflicting duplicate"):
        store.complete("key", {"value": 99})
    assert store.get("key").result == {"value": 42}
    store.close()


def test_unknown_outcome_blocks_completion_and_repeated_execution_claim(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    store.claim("key", "actuator_command", {"target": "safe-mode"})
    unknown = store.mark_unknown("key", "response timed out after dispatch")
    assert unknown.status is IdempotencyStatus.UNKNOWN
    assert not store.claim("key", "actuator_command", {"target": "safe-mode"}).created
    with pytest.raises(ValueError, match="must be reconciled"):
        store.complete("key", {"accepted": True})
    with pytest.raises(IdempotencyConflict, match="reason"):
        store.mark_unknown("key", "different explanation")
    store.close()


def test_unknown_outcome_requires_evidence_for_explicit_reconciliation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    store.claim("key", "actuator_command", {"target": "safe-mode"})
    store.mark_unknown("key", "connection lost")
    with pytest.raises(ValueError, match="evidence"):
        store.reconcile_completed("key", {"accepted": True}, evidence=" ")
    resolved = store.reconcile_completed(
        "key", {"accepted": True}, evidence="controller audit record 8472"
    )
    assert resolved.status is IdempotencyStatus.COMPLETED
    assert resolved.result == {"accepted": True}
    store.close()


def test_reconciliation_is_durable_and_duplicate_reconciliation_is_idempotent(tmp_path):
    path = tmp_path / "idempotency.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("key", "inspect", {"component": "brake"})
    store.mark_unknown("key", "acknowledgement lost")
    store.reconcile_completed("key", {"inspection_id": "r-12"}, evidence="signed report r-12")
    store.close()

    reopened = CommandIdempotencyStore(path)
    repeated = reopened.reconcile_completed(
        "key", {"inspection_id": "r-12"}, evidence="same report rechecked"
    )
    assert repeated.status is IdempotencyStatus.COMPLETED
    assert repeated.result == {"inspection_id": "r-12"}
    audit = reopened._connection.execute(
        "SELECT idempotency_key, evidence FROM command_idempotency_reconciliation ORDER BY sequence"
    ).fetchall()
    assert [(row["idempotency_key"], row["evidence"]) for row in audit] == [
        ("key", "signed report r-12")
    ]
    reopened.close()


def test_concurrent_claims_create_exactly_one_new_claim(tmp_path):
    path = tmp_path / "idempotency.sqlite3"
    first_store = CommandIdempotencyStore(path)
    second_store = CommandIdempotencyStore(path)
    def claim(store):
        return store.claim("shared", "calibrate", {"axis": "z"}).created
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(claim, (first_store, second_store)))
    assert sorted(created) == [False, True]
    first_store.close()
    second_store.close()


@pytest.mark.parametrize("key,name,payload", [
    (" ", "command", {}),
    ("key", " ", {}),
    ("key", "command", {"bad": object()}),
    ("key", "command", {"bad": float("nan")}),
])
def test_invalid_claim_input_is_rejected_without_creating_record(tmp_path, key, name, payload):
    store = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    with pytest.raises(ValueError):
        store.claim(key, name, payload)
    assert store.get("key") is None
    store.close()
