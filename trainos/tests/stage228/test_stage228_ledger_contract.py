import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_identical_claim_is_read_only_and_does_not_reset_dispatch_reservation(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(db)
    try:
        first = store.claim("key-228", "move", {"x": 1}, execution_id="exec-228")
        assert first.created is True
        assert store.reserve_dispatch("key-228") is True
        before = store.get("key-228")
        repeated = store.claim("key-228", "move", {"x": 1}, execution_id="exec-228")
        after = store.get("key-228")
        assert repeated.created is False
        assert repeated.record == before == after
        assert after.dispatch_started is True
        assert after.dispatch_generation == 1
    finally:
        store.close()
