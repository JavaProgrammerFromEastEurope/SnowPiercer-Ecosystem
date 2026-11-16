from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_invalid_audit_decision_is_reported(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('k394','charge',{'amount':394})
        store._connection.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL, evidence TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT '', decision TEXT NOT NULL DEFAULT 'completed', dispatch_generation INTEGER NOT NULL DEFAULT 0)")
        store._connection.execute("INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,decision,dispatch_generation) VALUES ('k394','proof','mystery',0)")
        assert any('invalid decision' in f for f in store.check_integrity())
    finally: store.close()
