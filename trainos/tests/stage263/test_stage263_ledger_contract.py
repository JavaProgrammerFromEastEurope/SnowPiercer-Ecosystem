from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_reconciliation_persists_audit_evidence(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        store.claim("key-263", "move", {"x": 1}, execution_id="exec-263")
        store.reserve_dispatch("key-263")
        store.mark_unknown("key-263", "ack timeout")
        completed = store.reconcile_completed("key-263", {"ok": True}, evidence="provider-receipt-263", execution_id="exec-263")
        assert completed.status is IdempotencyStatus.COMPLETED
        audit = store._connection.execute("SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=?", ("key-263",)).fetchone()
        assert tuple(audit) == ("provider-receipt-263", "completed", 1)
    finally:
        store.close()
