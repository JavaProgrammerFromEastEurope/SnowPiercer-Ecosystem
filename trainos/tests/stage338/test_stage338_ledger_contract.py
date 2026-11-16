from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_dispatch_requires_bound_execution_identity(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-338", "charge", {"amount": 338})
        assert store.reserve_dispatch("key-338") is False
        record = store.get("key-338")
        assert record.dispatch_started is False
        assert record.dispatch_generation == 0
    finally:
        store.close()
