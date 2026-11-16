import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_unknown_reason_cannot_be_overwritten_by_conflicting_reason(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-243", "move", {"x": 1})
        original = store.mark_unknown("key-243", "ack timeout")
        with pytest.raises(IdempotencyConflict, match="conflicting unknown-outcome reason"):
            store.mark_unknown("key-243", "device unreachable")
        assert store.get("key-243") == original
        assert store.get("key-243").status is IdempotencyStatus.UNKNOWN
    finally:
        store.close()
