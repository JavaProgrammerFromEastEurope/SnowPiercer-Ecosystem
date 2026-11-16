from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_reconciliation_audit_survives_database_reopen(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("key-317", "move", {"x": 1}, execution_id="exec-317")
    store.mark_unknown("key-317", "ack timeout")
    completed = store.reconcile_completed("key-317", {"ok": True}, evidence="provider receipt 317", execution_id="exec-317")
    store.close()
    reopened = CommandIdempotencyStore(path)
    try:
        assert reopened.get("key-317") == completed
        assert reopened.get("key-317").status is IdempotencyStatus.COMPLETED
        row = reopened._connection.execute("SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=?", ("key-317",)).fetchone()
        assert tuple(row) == ("provider receipt 317", "completed", 0)
    finally:
        reopened.close()
