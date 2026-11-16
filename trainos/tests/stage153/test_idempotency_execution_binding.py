import sqlite3

import pytest

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
    IdempotencyStatus,
)


def test_bound_execution_id_must_match_for_repeated_claim_and_completion(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "bound.sqlite3")
    first = store.claim("idem-1", "deploy", {"target": "A"}, execution_id="exec-1")
    assert first.created
    assert first.record.execution_id == "exec-1"

    repeated = store.claim("idem-1", "deploy", {"target": "A"}, execution_id="exec-1")
    assert not repeated.created
    with pytest.raises(IdempotencyConflict, match="different execution"):
        store.claim("idem-1", "deploy", {"target": "A"}, execution_id="exec-2")
    with pytest.raises(IdempotencyConflict, match="requires matching"):
        store.complete("idem-1", {"ok": True})
    with pytest.raises(IdempotencyConflict, match="does not match"):
        store.complete("idem-1", {"ok": True}, execution_id="exec-2")

    completed = store.complete("idem-1", {"ok": True}, execution_id="exec-1")
    assert completed.status is IdempotencyStatus.COMPLETED
    assert completed.execution_id == "exec-1"
    store.close()


def test_one_execution_id_cannot_be_bound_to_two_idempotency_keys(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "unique-execution.sqlite3")
    store.claim("idem-a", "actuate", {"channel": 2}, execution_id="exec-shared")
    with pytest.raises(IdempotencyConflict, match="already bound"):
        store.claim("idem-b", "actuate", {"channel": 2}, execution_id="exec-shared")
    assert store.get("idem-a").execution_id == "exec-shared"
    assert store.get("idem-b") is None
    store.close()


def test_unknown_reconciliation_requires_the_original_execution_binding(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "unknown-bound.sqlite3")
    store.claim("idem", "move", {"position": 10}, execution_id="exec-10")
    store.mark_unknown("idem", "external acknowledgement lost")
    with pytest.raises(IdempotencyConflict, match="does not match"):
        store.reconcile_completed(
            "idem", {"position": 10}, evidence="controller audit", execution_id="exec-other"
        )
    with pytest.raises(IdempotencyConflict, match="requires matching"):
        store.reconcile_completed("idem", {"position": 10}, evidence="controller audit")
    resolved = store.reconcile_completed(
        "idem", {"position": 10}, evidence="controller audit record 12", execution_id="exec-10"
    )
    assert resolved.status is IdempotencyStatus.COMPLETED
    assert resolved.execution_id == "exec-10"
    store.close()


def test_execution_binding_survives_restart(tmp_path):
    path = tmp_path / "restart.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("idem", "read", {"sensor": "temperature"}, execution_id="exec-read-1")
    store.close()

    reopened = CommandIdempotencyStore(path)
    record = reopened.get("idem")
    assert record.execution_id == "exec-read-1"
    with pytest.raises(IdempotencyConflict):
        reopened.claim("idem", "read", {"sensor": "temperature"}, execution_id="exec-read-2")
    reopened.close()


def test_legacy_schema_is_migrated_without_losing_existing_records(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE command_idempotency (
            idempotency_key TEXT PRIMARY KEY, command_name TEXT NOT NULL, fingerprint TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('claimed', 'unknown', 'completed')),
            result_json TEXT, uncertainty_reason TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            CHECK((status = 'completed' AND result_json IS NOT NULL AND uncertainty_reason IS NULL)
               OR (status = 'unknown' AND result_json IS NULL AND uncertainty_reason IS NOT NULL)
               OR (status = 'claimed' AND result_json IS NULL AND uncertainty_reason IS NULL))
        )"""
    )
    import hashlib, json
    fingerprint = hashlib.sha256(json.dumps({"command_name": "legacy", "payload": {}}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    connection.execute(
        "INSERT INTO command_idempotency(idempotency_key, command_name, fingerprint, status) VALUES (?, ?, ?, 'claimed')",
        ("legacy-key", "legacy", fingerprint),
    )
    connection.commit()
    connection.close()

    store = CommandIdempotencyStore(path)
    record = store.get("legacy-key")
    assert record is not None and record.execution_id is None
    assert not store.claim("legacy-key", "legacy", {}).created
    with pytest.raises(IdempotencyConflict, match="cannot bind"):
        store.claim("legacy-key", "legacy", {}, execution_id="new-binding")
    store.close()
