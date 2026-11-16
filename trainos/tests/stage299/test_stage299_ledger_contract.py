import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_unknown_reason_cannot_be_changed_on_repeat(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-299", "move", {"x": 1}, execution_id="exec-299")
        first = store.mark_unknown("key-299", "ack timeout")
        with pytest.raises(IdempotencyConflict, match="conflicting unknown-outcome reason"):
            store.mark_unknown("key-299", "different timeout")
        assert store.get("key-299") == first
        assert store.get("key-299").status is IdempotencyStatus.UNKNOWN
    finally:
        store.close()
