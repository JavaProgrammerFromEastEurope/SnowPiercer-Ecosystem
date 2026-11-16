import pytest

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
    IdempotencyStatus,
)


def _unknown(path):
    store = CommandIdempotencyStore(path)
    store.claim("key-174", "set_route", {"route": "R-4"}, execution_id="exec-174")
    assert store.reserve_dispatch("key-174") is True
    store.mark_unknown("key-174", "process stopped before acknowledgement")
    store.reconcile_not_executed(
        "key-174", evidence="controller receipt #100 proves no acceptance", execution_id="exec-174"
    )
    return store


def test_old_not_executed_evidence_cannot_be_reused_after_new_dispatch(tmp_path):
    path = tmp_path / "old-evidence-after-dispatch.sqlite3"
    store = _unknown(path)
    assert store.reserve_dispatch("key-174") is True
    record = store.get("key-174")
    assert record.dispatch_generation == 2
    store.mark_unknown("key-174", "second dispatch has no acknowledgement")
    store.close()

    reopened = CommandIdempotencyStore(path)
    try:
        record = reopened.get("key-174")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.dispatch_started is True
        assert record.dispatch_generation == 2
        assert reopened.reserve_dispatch("key-174") is False
        with pytest.raises(IdempotencyConflict, match="predates a later dispatch"):
            reopened.reconcile_not_executed(
                "key-174",
                evidence="controller receipt #100 proves no acceptance",
                execution_id="exec-174",
            )
        resolved = reopened.reconcile_not_executed(
            "key-174",
            evidence="controller receipt #101 independently proves second request was not accepted",
            execution_id="exec-174",
        )
        assert resolved.status is IdempotencyStatus.CLAIMED
        assert resolved.dispatch_started is False
        assert resolved.dispatch_generation == 2
        assert reopened.reserve_dispatch("key-174") is True
        assert reopened.reserve_dispatch("key-174") is False
        history = reopened._connection.execute(
            "SELECT evidence, dispatch_generation FROM command_idempotency_reconciliation "
            "WHERE idempotency_key=? ORDER BY sequence", ("key-174",)
        ).fetchall()
        assert [(row["evidence"], row["dispatch_generation"]) for row in history] == [
            ("controller receipt #100 proves no acceptance", 1),
            ("controller receipt #101 independently proves second request was not accepted", 2),
        ]
    finally:
        reopened.close()


def test_crash_after_re_reservation_preserves_generation_and_blocks_replay(tmp_path):
    path = tmp_path / "crash-after-rereserve.sqlite3"
    store = _unknown(path)
    assert store.reserve_dispatch("key-174") is True
    store.close()  # Simulate process termination before acknowledgement persistence.

    reopened = CommandIdempotencyStore(path)
    try:
        record = reopened.get("key-174")
        assert record.dispatch_generation == 2
        assert record.dispatch_started is True
        assert reopened.reserve_dispatch("key-174") is False
        rows = reopened._connection.execute(
            "SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key='key-174'"
        ).fetchone()[0]
        assert rows == 1
    finally:
        reopened.close()
