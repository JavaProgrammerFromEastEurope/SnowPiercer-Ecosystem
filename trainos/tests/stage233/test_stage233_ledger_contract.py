import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_not_executed_evidence_from_prior_dispatch_generation_cannot_be_reused(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-233", "move", {"x": 1}, execution_id="exec-233")
        assert store.reserve_dispatch("key-233") is True
        store.mark_unknown("key-233", "first acknowledgement lost")
        store.reconcile_not_executed("key-233", evidence="proof-generation-1", execution_id="exec-233")
        assert store.reserve_dispatch("key-233") is True
        store.mark_unknown("key-233", "second acknowledgement lost")
        with pytest.raises(IdempotencyConflict, match="predates a later dispatch"):
            store.reconcile_not_executed("key-233", evidence="proof-generation-1", execution_id="exec-233")
        record = store.get("key-233")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.dispatch_generation == 2
    finally:
        store.close()
