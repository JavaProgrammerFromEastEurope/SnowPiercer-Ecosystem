from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_duplicate_claim_preserves_dispatch_reservation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-218", "move", {"x": 1}, execution_id="exec-218")
        assert first.created is True
        assert store.reserve_dispatch("key-218") is True
        again = store.claim("key-218", "move", {"x": 1}, execution_id="exec-218")
        assert again.created is False
        assert again.record.dispatch_started is True
        assert again.record.dispatch_generation == 1
        assert store.reserve_dispatch("key-218") is False
    finally:
        store.close()
