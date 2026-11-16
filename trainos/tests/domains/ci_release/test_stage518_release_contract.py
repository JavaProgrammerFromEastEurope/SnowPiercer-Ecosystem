from contextlib import closing
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_missing_audit_column_is_reported_read_only(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    with closing(sqlite3.connect(backup)) as conn, conn:
        conn.execute("ALTER TABLE command_idempotency_reconciliation RENAME TO audit_old")
        conn.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER PRIMARY KEY, idempotency_key TEXT NOT NULL, evidence TEXT NOT NULL, recorded_at TEXT NOT NULL, decision TEXT NOT NULL)")
        conn.execute("INSERT INTO command_idempotency_reconciliation SELECT sequence,idempotency_key,evidence,recorded_at,decision FROM audit_old")
        conn.execute("DROP TABLE audit_old")
    before=backup.read_bytes()
    findings=CommandIdempotencyStore.validate_backup(backup)
    assert any("audit: missing columns" in item and "dispatch_generation" in item for item in findings)
    assert backup.read_bytes()==before
