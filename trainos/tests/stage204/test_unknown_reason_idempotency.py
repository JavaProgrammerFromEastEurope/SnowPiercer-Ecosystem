import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_unknown_transition_is_idempotent_for_same_reason_only(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-204", "move", {"x": 1}, execution_id="exec-204")
        first = store.mark_unknown("key-204", "ack timeout")
        again = store.mark_unknown("key-204", "ack timeout")
        assert again == first
        with pytest.raises(IdempotencyConflict, match="conflicting unknown-outcome"):
            store.mark_unknown("key-204", "transport reset")
        assert store.get("key-204") == first
        assert first.status is IdempotencyStatus.UNKNOWN
    finally:
        store.close()
