import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_blank_unknown_reason_does_not_change_claimed_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        original = store.claim("key-209", "move", {"x": 1}, execution_id="exec-209").record
        with pytest.raises(ValueError, match="reason must not be empty"):
            store.mark_unknown("key-209", "  ")
        assert store.get("key-209") == original
        assert store.get("key-209").status is IdempotencyStatus.CLAIMED
    finally:
        store.close()
