import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_nonfinite_result_is_rejected_and_claim_remains_claimed(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-202", "move", {"x": 1}, execution_id="exec-202")
        with pytest.raises(ValueError, match="JSON-serializable"):
            store.complete("key-202", {"value": float("inf")}, execution_id="exec-202")
        record = store.get("key-202")
        assert record.status is IdempotencyStatus.CLAIMED
        assert record.result is None
    finally:
        store.close()
