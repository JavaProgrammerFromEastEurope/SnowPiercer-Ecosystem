import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_not_executed_evidence_for_same_generation_is_rejected(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-224", "move", {"x": 1}, execution_id="exec-224")
        store.reserve_dispatch("key-224")
        store.mark_unknown("key-224", "ack timeout")
        store.reconcile_not_executed("key-224", evidence="proof-A", execution_id="exec-224")
        with pytest.raises(IdempotencyConflict, match="conflicting evidence"):
            store.reconcile_not_executed("key-224", evidence="proof-B", execution_id="exec-224")
    finally:
        store.close()
