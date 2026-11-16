import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_old_not_executed_evidence_is_stale_after_new_dispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-206", "move", {"x": 1}, execution_id="exec-206")
        assert store.reserve_dispatch("key-206") is True
        store.mark_unknown("key-206", "first ack timeout")
        store.reconcile_not_executed("key-206", evidence="provider-proof-206", execution_id="exec-206")
        assert store.reserve_dispatch("key-206") is True
        store.mark_unknown("key-206", "second ack timeout")
        with pytest.raises(IdempotencyConflict, match="predates a later dispatch"):
            store.reconcile_not_executed("key-206", evidence="provider-proof-206", execution_id="exec-206")
        assert store.get("key-206").status.value == "unknown"
        assert store.get("key-206").dispatch_generation == 2
    finally:
        store.close()
