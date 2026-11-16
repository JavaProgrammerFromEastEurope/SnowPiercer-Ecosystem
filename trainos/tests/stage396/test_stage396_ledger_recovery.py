from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_blank_audit_evidence_is_reported_without_repair(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('k396','charge',{'amount':396})
        store._connection.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL, evidence TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT '', decision TEXT NOT NULL DEFAULT 'not_executed', dispatch_generation INTEGER NOT NULL DEFAULT 0)")
        store._connection.execute("INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,decision,dispatch_generation) VALUES ('k396','   ','not_executed',0)")
        before=store._connection.execute('SELECT evidence FROM command_idempotency_reconciliation').fetchone()[0]
        findings=store.check_integrity()
        after=store._connection.execute('SELECT evidence FROM command_idempotency_reconciliation').fetchone()[0]
        assert any('empty evidence' in f for f in findings) and before == after == '   '
    finally: store.close()
