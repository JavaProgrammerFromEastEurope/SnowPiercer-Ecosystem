"""Unknown command outcomes require an explicit, durable reconciliation decision."""
import pytest

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
    IdempotencyStatus,
)


def _unknown_store(path):
    store = CommandIdempotencyStore(path)
    store.claim("key-172", "inspect_controller", {"unit": "C-17"}, execution_id="exec-172")
    assert store.reserve_dispatch("key-172") is True
    store.mark_unknown("key-172", "external acknowledgement lost")
    return store


def test_explicit_not_executed_evidence_allows_one_new_reservation_after_restart(tmp_path):
    path = tmp_path / "not-executed.sqlite3"
    store = _unknown_store(path)
    store.close()

    reopened = CommandIdempotencyStore(path)
    try:
        record = reopened.reconcile_not_executed(
            "key-172", evidence="controller ledger confirms no command accepted", execution_id="exec-172"
        )
        assert record.status is IdempotencyStatus.CLAIMED
        assert record.dispatch_started is False
        # The explicit reconciliation permits a new reservation, but only once.
        assert reopened.reserve_dispatch("key-172") is True
        assert reopened.reserve_dispatch("key-172") is False
        audit = reopened._connection.execute(
            "SELECT decision, evidence FROM command_idempotency_reconciliation WHERE idempotency_key=?",
            ("key-172",),
        ).fetchall()
        assert [(row["decision"], row["evidence"]) for row in audit] == [
            ("not_executed", "controller ledger confirms no command accepted")
        ]
    finally:
        reopened.close()


def test_empty_or_wrong_binding_evidence_cannot_reconcile_unknown_outcome(tmp_path):
    store = _unknown_store(tmp_path / "invalid-evidence.sqlite3")
    try:
        with pytest.raises(ValueError, match="evidence"):
            store.reconcile_not_executed("key-172", evidence=" ", execution_id="exec-172")
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.reconcile_not_executed("key-172", evidence="verified no dispatch", execution_id="other")
        assert store.get("key-172").status is IdempotencyStatus.UNKNOWN
        assert store.get("key-172").dispatch_started is True
    finally:
        store.close()


def test_repeated_same_decision_is_idempotent_but_conflicting_evidence_is_blocked(tmp_path):
    store = _unknown_store(tmp_path / "conflicting-evidence.sqlite3")
    try:
        evidence = "signed controller receipt states command was not accepted"
        first = store.reconcile_not_executed("key-172", evidence=evidence, execution_id="exec-172")
        repeated = store.reconcile_not_executed("key-172", evidence=evidence, execution_id="exec-172")
        assert first == repeated
        with pytest.raises(IdempotencyConflict, match="conflicting evidence"):
            store.reconcile_not_executed(
                "key-172", evidence="different report says unknown", execution_id="exec-172"
            )
        rows = store._connection.execute(
            "SELECT decision, evidence FROM command_idempotency_reconciliation WHERE idempotency_key=?",
            ("key-172",),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["decision"] == "not_executed"
        assert rows[0]["evidence"] == evidence
    finally:
        store.close()


def test_legacy_reconciliation_table_migrates_decision_column(tmp_path):
    path = tmp_path / "legacy-reconciliation.sqlite3"
    store = CommandIdempotencyStore(path)
    store._connection.execute(
        "CREATE TABLE command_idempotency_reconciliation ("
        "sequence INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL, "
        "evidence TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT 'now')"
    )
    store._connection.execute(
        "INSERT INTO command_idempotency_reconciliation(idempotency_key, evidence) VALUES (?, ?)",
        ("legacy-key", "old evidence"),
    )
    store._connection.commit()
    store.claim("legacy-key", "inspect", {}, execution_id="legacy-exec")
    store.mark_unknown("legacy-key", "unknown after restart")
    resolved = store.reconcile_not_executed(
        "legacy-key", evidence="verified no action", execution_id="legacy-exec"
    )
    assert resolved.status is IdempotencyStatus.CLAIMED
    columns = {row["name"] for row in store._connection.execute(
        "PRAGMA table_info(command_idempotency_reconciliation)"
    ).fetchall()}
    assert "decision" in columns
    store.close()
