from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_duplicate_claim_does_not_reset_durable_dispatch_reservation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-269", "move", {"x": 1}, execution_id="exec-269")
        assert first.created is True
        assert store.reserve_dispatch("key-269") is True
        second = store.claim("key-269", "move", {"x": 1}, execution_id="exec-269")
        assert second.created is False
        assert second.record.dispatch_started is True
        assert second.record.dispatch_generation == 1
        assert store.reserve_dispatch("key-269") is False
    finally:
        store.close()
