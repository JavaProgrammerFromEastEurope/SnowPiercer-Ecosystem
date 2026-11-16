from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_identical_not_executed_reconciliation_is_idempotent_before_redispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-251", "move", {"x": 1}, execution_id="exec-251")
        store.reserve_dispatch("key-251")
        store.mark_unknown("key-251", "ack timeout")
        first = store.reconcile_not_executed("key-251", evidence="authoritative-absence-251", execution_id="exec-251")
        second = store.reconcile_not_executed("key-251", evidence="authoritative-absence-251", execution_id="exec-251")
        assert first == second
        assert second.status is IdempotencyStatus.CLAIMED
        assert second.dispatch_started is False
        assert second.dispatch_generation == 1
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation").fetchone()[0] == 1
    finally:
        store.close()
