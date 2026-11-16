import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_old_not_executed_proof_cannot_be_reused_after_new_dispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-295", "move", {"x": 1}, execution_id="exec-295")
        assert store.reserve_dispatch("key-295") is True
        store.mark_unknown("key-295", "ack timeout 1")
        store.reconcile_not_executed("key-295", evidence="provider-says-absent", execution_id="exec-295")
        assert store.reserve_dispatch("key-295") is True
        store.mark_unknown("key-295", "ack timeout 2")
        before = store.get("key-295")
        with pytest.raises(IdempotencyConflict, match="predates a later dispatch"):
            store.reconcile_not_executed("key-295", evidence="provider-says-absent", execution_id="exec-295")
        assert store.get("key-295") == before
    finally:
        store.close()
