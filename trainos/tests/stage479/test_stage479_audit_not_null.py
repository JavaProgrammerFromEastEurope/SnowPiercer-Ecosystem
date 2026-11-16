from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from pathlib import Path
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def make_backup(tmp_path: Path) -> Path:
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("key-1", "charge", {"cents": 250})
    store.mark_unknown("key-1", reason="provider response missing")
    store.reconcile_completed("key-1", {"provider_ref": "ref-1"}, evidence="provider lookup confirmed completion")
    backup = tmp_path / "backup.db"
    store.backup_to(backup)
    store.close()
    return backup

def test_backup_rejects_nullable_required_audit_column(tmp_path):
    backup = make_backup(tmp_path)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("ALTER TABLE command_idempotency_reconciliation RENAME TO audit_old")
        conn.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL, evidence TEXT, recorded_at TEXT NOT NULL, decision TEXT NOT NULL, dispatch_generation INTEGER NOT NULL)")
        conn.execute("INSERT INTO command_idempotency_reconciliation SELECT * FROM audit_old")
        conn.execute("DROP TABLE audit_old")
    assert any("column evidence must be NOT NULL" in x for x in CommandIdempotencyStore.validate_backup(backup))
