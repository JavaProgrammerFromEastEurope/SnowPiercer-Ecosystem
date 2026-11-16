from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_validation_rejects_audit_table_without_sequence_primary_key(tmp_path):
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("k", "charge", {"cents": 10})
    store.mark_unknown("k", reason="timeout")
    store.reconcile_completed("k", {"ref": "r1"}, evidence="provider confirms completion")
    backup = tmp_path / "backup.db"
    store.backup_to(backup)
    store.close()
    with managed_sqlite_connection(backup) as conn:
        conn.execute("ALTER TABLE command_idempotency_reconciliation RENAME TO old_audit")
        conn.execute("CREATE TABLE command_idempotency_reconciliation(sequence INTEGER, idempotency_key TEXT NOT NULL, evidence TEXT NOT NULL, recorded_at TEXT NOT NULL, decision TEXT NOT NULL, dispatch_generation INTEGER NOT NULL)")
        conn.execute("INSERT INTO command_idempotency_reconciliation SELECT * FROM old_audit")
        conn.execute("DROP TABLE old_audit")
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("sequence must be the primary key" in item for item in findings)
