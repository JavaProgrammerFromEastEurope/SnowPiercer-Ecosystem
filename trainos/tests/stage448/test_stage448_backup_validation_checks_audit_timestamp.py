from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_backup_validation_checks_audit_timestamp(tmp_path):
    store = make_store(tmp_path)
    try:
        store.claim("key", "cmd", {"v": 1})
        store.mark_unknown("key", reason="timeout")
        store.reconcile_not_executed("key", evidence="provider confirmed not sent")
        backup = tmp_path / "backup.db"
        store.backup_to(backup)
    finally:
        store.close()
    import sqlite3
    conn = sqlite3.connect(backup)
    conn.execute("UPDATE command_idempotency_reconciliation SET recorded_at = ''")
    conn.commit(); conn.close()
    assert any("empty recorded_at" in item for item in CommandIdempotencyStore.validate_backup(backup))
