import pytest

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
    IdempotencyStatus,
)


def _prepare_unknown(path, key, execution_id):
    store = CommandIdempotencyStore(path)
    store.claim(key, "inspect_controller", {"unit": "C-17"}, execution_id=execution_id)
    assert store.reserve_dispatch(key) is True
    store.mark_unknown(key, "process stopped before acknowledgement was recorded")
    return store


def test_not_executed_decision_survives_restart_before_new_reservation(tmp_path):
    path = tmp_path / "reconcile-before-reserve.sqlite3"
    store = _prepare_unknown(path, "key-173-a", "exec-173-a")
    evidence = "signed controller ledger confirms request was not accepted"
    try:
        resolved = store.reconcile_not_executed(
            "key-173-a", evidence=evidence, execution_id="exec-173-a"
        )
        assert resolved.status is IdempotencyStatus.CLAIMED
        assert resolved.dispatch_started is False
    finally:
        store.close()

    reopened = CommandIdempotencyStore(path)
    try:
        record = reopened.get("key-173-a")
        assert record is not None
        assert record.status is IdempotencyStatus.CLAIMED
        assert record.dispatch_started is False
        rows = reopened._connection.execute(
            "SELECT decision, evidence FROM command_idempotency_reconciliation "
            "WHERE idempotency_key=? ORDER BY sequence", ("key-173-a",)
        ).fetchall()
        assert [(row["decision"], row["evidence"]) for row in rows] == [
            ("not_executed", evidence)
        ]
        assert reopened.reconcile_not_executed(
            "key-173-a", evidence=evidence, execution_id="exec-173-a"
        ) == record
        assert reopened.reserve_dispatch("key-173-a") is True
        assert reopened.reserve_dispatch("key-173-a") is False
    finally:
        reopened.close()


def test_restart_preserves_evidence_and_rejects_conflicting_reconciliation(tmp_path):
    path = tmp_path / "reconcile-conflict-after-restart.sqlite3"
    store = _prepare_unknown(path, "key-173-b", "exec-173-b")
    evidence = "authoritative device ledger says command was not accepted"
    store.reconcile_not_executed(
        "key-173-b", evidence=evidence, execution_id="exec-173-b"
    )
    store.close()

    reopened = CommandIdempotencyStore(path)
    try:
        with pytest.raises(IdempotencyConflict, match="conflicting evidence"):
            reopened.reconcile_not_executed(
                "key-173-b",
                evidence="a different report claims the command may have executed",
                execution_id="exec-173-b",
            )
        record = reopened.get("key-173-b")
        assert record is not None
        assert record.status is IdempotencyStatus.CLAIMED
        assert record.dispatch_started is False
        rows = reopened._connection.execute(
            "SELECT decision, evidence FROM command_idempotency_reconciliation "
            "WHERE idempotency_key=?", ("key-173-b",)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["decision"] == "not_executed"
        assert rows[0]["evidence"] == evidence
    finally:
        reopened.close()


def test_reconciliation_restart_does_not_change_independent_command(tmp_path):
    path = tmp_path / "independent-commands.sqlite3"
    store = _prepare_unknown(path, "key-173-c", "exec-173-c")
    store.claim("key-173-independent", "read_temperature", {"unit": "C-18"}, execution_id="exec-173-independent")
    try:
        store.reconcile_not_executed(
            "key-173-c", evidence="device receipt confirms no acceptance", execution_id="exec-173-c"
        )
    finally:
        store.close()

    reopened = CommandIdempotencyStore(path)
    try:
        independent = reopened.get("key-173-independent")
        assert independent is not None
        assert independent.status is IdempotencyStatus.CLAIMED
        assert independent.dispatch_started is False
        assert reopened.reserve_dispatch("key-173-independent") is True
        assert reopened.reserve_dispatch("key-173-c") is True
    finally:
        reopened.close()
