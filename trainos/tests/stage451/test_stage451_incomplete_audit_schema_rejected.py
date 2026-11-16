from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_incomplete_audit_schema_rejected(tmp_path):
    store = make_store(tmp_path)
    try:
        store.claim("key", "cmd", {"v": 1})
        backup = tmp_path / "backup.db"; store.backup_to(backup)
    finally: store.close()
    import sqlite3
    conn = sqlite3.connect(backup)
    conn.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER PRIMARY KEY, idempotency_key TEXT, evidence TEXT, decision TEXT, dispatch_generation INTEGER)")
    conn.commit(); conn.close()
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("missing columns: recorded_at" in item for item in findings)
