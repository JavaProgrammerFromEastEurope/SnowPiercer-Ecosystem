from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_dispatch_reservation_is_single_use_per_generation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-339", "charge", {"amount": 339}, execution_id="exec-339")
        assert store.reserve_dispatch("key-339") is True
        assert store.reserve_dispatch("key-339") is False
        record = store.get("key-339")
        assert record.dispatch_started is True
        assert record.dispatch_generation == 1
    finally:
        store.close()
