from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_backup_validation_checks_sequence_primary_key(tmp_path):
    store = make_store(tmp_path)
    try:
        store.claim("key", "cmd", {"v": 1})
        store.mark_unknown("key", reason="timeout")
        store.reconcile_not_executed("key", evidence="provider confirmed not sent")
        backup = tmp_path / "backup.db"
        store.backup_to(backup)
    finally: store.close()
    import sqlite3
    conn = sqlite3.connect(backup)
    conn.execute("ALTER TABLE command_idempotency_reconciliation RENAME TO audit_old")
    conn.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER, idempotency_key TEXT, evidence TEXT, recorded_at TEXT, decision TEXT, dispatch_generation INTEGER)")
    conn.execute("INSERT INTO command_idempotency_reconciliation SELECT * FROM audit_old")
    conn.commit(); conn.close()
    assert any("sequence must be the primary key" in item for item in CommandIdempotencyStore.validate_backup(backup))
