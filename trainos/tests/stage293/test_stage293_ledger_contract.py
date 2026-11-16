import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

@pytest.mark.parametrize("reason", ["", "   "])
def test_blank_unknown_reason_does_not_change_state(tmp_path, reason):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-293", "move", {"x": 1}, execution_id="exec-293")
        before = store.get("key-293")
        with pytest.raises(ValueError, match="reason must not be empty"):
            store.mark_unknown("key-293", reason)
        assert store.get("key-293") == before
        assert before.status is IdempotencyStatus.CLAIMED
    finally:
        store.close()
