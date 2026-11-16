from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_unknown_command_cannot_be_dispatched_again_without_reconciliation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-341", "charge", {"amount": 341}, execution_id="exec-341")
        assert store.reserve_dispatch("key-341") is True
        store.mark_unknown("key-341", "provider timeout")
        assert store.reserve_dispatch("key-341") is False
        record = store.get("key-341")
        assert record.status.value == "unknown"
        assert record.dispatch_generation == 1
        assert record.dispatch_started is True
    finally:
        store.close()
