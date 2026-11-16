import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus


def test_not_executed_evidence_cannot_be_reused_after_new_dispatch_generation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-277", "move", {"x": 1}, execution_id="exec-277")
        assert store.reserve_dispatch("key-277") is True
        store.mark_unknown("key-277", "ack timeout")
        store.reconcile_not_executed("key-277", evidence="provider-confirms-absent", execution_id="exec-277")
        assert store.reserve_dispatch("key-277") is True
        store.mark_unknown("key-277", "second ack timeout")
        before = store.get("key-277")
        with pytest.raises(IdempotencyConflict, match="evidence predates a later dispatch attempt"):
            store.reconcile_not_executed("key-277", evidence="provider-confirms-absent", execution_id="exec-277")
        assert store.get("key-277") == before
        assert store.get("key-277").status is IdempotencyStatus.UNKNOWN
        assert store.get("key-277").dispatch_generation == 2
    finally:
        store.close()
