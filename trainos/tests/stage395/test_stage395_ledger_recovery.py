from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_future_audit_generation_is_reported(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('k395','charge',{'amount':395})
        store._connection.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL, evidence TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT '', decision TEXT NOT NULL DEFAULT 'not_executed', dispatch_generation INTEGER NOT NULL DEFAULT 0)")
        store._connection.execute("INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,decision,dispatch_generation) VALUES ('k395','proof','not_executed',99)")
        assert any('invalid dispatch generation' in f for f in store.check_integrity())
    finally: store.close()
