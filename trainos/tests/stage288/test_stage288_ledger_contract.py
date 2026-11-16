from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_equivalent_repeat_claim_preserves_dispatch_reservation(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        first = store.claim("key-288", "move", {"x": 1}, execution_id="exec-288")
        assert first.created is True
        assert store.reserve_dispatch("key-288") is True
        before = store.get("key-288")
        repeated = store.claim(" key-288 ", "move", {"x": 1}, execution_id="exec-288")
        assert repeated.created is False
        assert repeated.record == before
        assert repeated.record.dispatch_started is True
        assert repeated.record.dispatch_generation == 1
    finally:
        store.close()
