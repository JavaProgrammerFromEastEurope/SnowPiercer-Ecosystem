import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_unknown_transition_is_idempotent_only_for_same_reason(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-220", "move", {"x": 1})
        first = store.mark_unknown("key-220", "ack timeout")
        second = store.mark_unknown("key-220", "ack timeout")
        assert first.status is second.status is IdempotencyStatus.UNKNOWN
        with pytest.raises(IdempotencyConflict):
            store.mark_unknown("key-220", "different explanation")
        assert store.get("key-220").uncertainty_reason == "ack timeout"
    finally:
        store.close()
