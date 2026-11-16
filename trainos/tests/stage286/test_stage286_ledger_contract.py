from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_dispatch_generation_increments_only_after_explicit_not_executed_reconciliation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-286", "move", {"x": 1}, execution_id="exec-286")
        assert store.reserve_dispatch("key-286") is True
        assert store.get("key-286").dispatch_generation == 1
        store.mark_unknown("key-286", "ack timeout")
        assert store.get("key-286").dispatch_generation == 1
        store.reconcile_not_executed("key-286", evidence="provider-absent-286", execution_id="exec-286")
        assert store.get("key-286").dispatch_generation == 1
        assert store.reserve_dispatch("key-286") is True
        assert store.get("key-286").dispatch_generation == 2
    finally:
        store.close()
