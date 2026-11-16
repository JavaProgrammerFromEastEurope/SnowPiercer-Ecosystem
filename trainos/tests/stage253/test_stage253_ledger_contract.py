import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_old_not_executed_evidence_cannot_be_reused_after_new_dispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-253", "move", {"x": 1}, execution_id="exec-253")
        assert store.reserve_dispatch("key-253") is True
        store.mark_unknown("key-253", "first timeout")
        store.reconcile_not_executed("key-253", evidence="proof-253", execution_id="exec-253")
        assert store.reserve_dispatch("key-253") is True
        store.mark_unknown("key-253", "second timeout")
        before = store.get("key-253")
        with pytest.raises(IdempotencyConflict, match="predates a later dispatch"):
            store.reconcile_not_executed("key-253", evidence="proof-253", execution_id="exec-253")
        assert store.get("key-253") == before
    finally:
        store.close()
