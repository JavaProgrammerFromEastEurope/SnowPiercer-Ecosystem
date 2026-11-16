from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_duplicate_reconciliation_event_is_rejected(tmp_path):
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("k", "charge", {"cents": 10})
    store.mark_unknown("k", reason="timeout")
    store.reconcile_completed("k", {"ref": "r1"}, evidence="provider confirms completion")
    backup = tmp_path / "backup.db"
    store.backup_to(backup)
    store.close()
    with managed_sqlite_connection(backup) as conn:
        row = conn.execute("SELECT idempotency_key,evidence,recorded_at,decision,dispatch_generation FROM command_idempotency_reconciliation WHERE sequence=1").fetchone()
        conn.execute("INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,recorded_at,decision,dispatch_generation) VALUES(?,?,?,?,?)", row)
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("duplicate reconciliation event" in item for item in findings)
