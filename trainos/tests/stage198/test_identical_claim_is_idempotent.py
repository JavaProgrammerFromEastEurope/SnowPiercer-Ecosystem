import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_identical_claim_is_idempotent_and_does_not_reset_state(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-198", "move", {"x": 1}, execution_id="exec-198")
        assert first.created is True
        assert store.reserve_dispatch("key-198") is True
        second = store.claim("key-198", "move", {"x": 1}, execution_id="exec-198")
        assert second.created is False
        assert second.record == store.get("key-198")
        assert second.record.dispatch_generation == 1
        assert second.record.dispatch_started is True
    finally:
        store.close()
