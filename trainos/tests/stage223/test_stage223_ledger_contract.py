import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_not_executed_evidence_cannot_be_reused_after_later_dispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-223", "move", {"x": 1}, execution_id="exec-223")
        assert store.reserve_dispatch("key-223") is True
        store.mark_unknown("key-223", "ack timeout")
        store.reconcile_not_executed("key-223", evidence="provider-says-absent", execution_id="exec-223")
        assert store.reserve_dispatch("key-223") is True
        store.mark_unknown("key-223", "second ack timeout")
        with pytest.raises(IdempotencyConflict, match="predates a later dispatch"):
            store.reconcile_not_executed("key-223", evidence="provider-says-absent", execution_id="exec-223")
        assert store.get("key-223").uncertainty_reason == "second ack timeout"
    finally:
        store.close()
