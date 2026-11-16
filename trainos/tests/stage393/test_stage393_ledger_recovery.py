from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_orphan_audit_is_reported(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store._connection.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL, evidence TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT '', decision TEXT NOT NULL DEFAULT 'completed', dispatch_generation INTEGER NOT NULL DEFAULT 0)")
        store._connection.execute("INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,decision,dispatch_generation) VALUES ('missing393','evidence','not_executed',0)")
        findings=store.check_integrity()
        assert any("orphan idempotency key 'missing393'" in f for f in findings)
    finally: store.close()
