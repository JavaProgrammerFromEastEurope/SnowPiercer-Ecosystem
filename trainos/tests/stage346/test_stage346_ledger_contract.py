import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_not_executed_evidence_cannot_be_reused_after_new_dispatch_generation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-346", "charge", {"amount": 346}, execution_id="exec-346")
        assert store.reserve_dispatch("key-346") is True
        store.mark_unknown("key-346", "first timeout")
        store.reconcile_not_executed(
            "key-346", evidence="provider says not executed", execution_id="exec-346"
        )
        assert store.reserve_dispatch("key-346") is True
        store.mark_unknown("key-346", "second timeout")
        before = store.get("key-346")
        with pytest.raises(IdempotencyConflict):
            store.reconcile_not_executed(
                "key-346", evidence="provider says not executed", execution_id="exec-346"
            )
        assert store.get("key-346") == before
    finally:
        store.close()
