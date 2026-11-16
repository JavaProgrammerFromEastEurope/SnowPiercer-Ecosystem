from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_invalid_audit_decision_is_rejected(tmp_path):
    db=tmp_path/'ledger.db'; store=CommandIdempotencyStore(db)
    try:
        store.claim('k','noop',{}); store._ensure_reconciliation_table()
        store._connection.execute("INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,decision,dispatch_generation) VALUES('k','evidence','maybe',0)")
        store._connection.commit()
    finally: store.close()
    findings=CommandIdempotencyStore.validate_backup(db)
    assert any('invalid decision' in finding for finding in findings)
