from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_reconciling_already_completed_command_is_idempotent(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-301", "move", {"x": 1}, execution_id="exec-301")
        store.mark_unknown("key-301", "ack timeout")
        first = store.reconcile_completed("key-301", {"ok": True}, evidence="provider receipt", execution_id="exec-301")
        audit_count = store._connection.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation").fetchone()[0]
        repeated = store.reconcile_completed("key-301", {"ok": True}, evidence="provider receipt", execution_id="exec-301")
        after_count = store._connection.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation").fetchone()[0]
        assert repeated == first
        assert repeated.status is IdempotencyStatus.COMPLETED
        assert after_count == audit_count
    finally:
        store.close()
