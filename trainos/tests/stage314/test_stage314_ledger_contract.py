from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_not_executed_reconciliation_allows_one_new_dispatch_generation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-314", "move", {"x": 1}, execution_id="exec-314")
        assert store.reserve_dispatch("key-314") is True
        assert store.get("key-314").dispatch_generation == 1
        store.mark_unknown("key-314", "ack timeout")
        restored = store.reconcile_not_executed("key-314", evidence="provider confirms absent", execution_id="exec-314")
        assert restored.status is IdempotencyStatus.CLAIMED
        assert restored.dispatch_started is False
        assert restored.dispatch_generation == 1
        assert store.reserve_dispatch("key-314") is True
        again = store.get("key-314")
        assert again.dispatch_generation == 2
        assert store.reserve_dispatch("key-314") is False
    finally:
        store.close()
