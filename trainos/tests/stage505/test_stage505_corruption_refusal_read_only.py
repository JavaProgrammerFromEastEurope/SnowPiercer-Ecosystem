from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_validation_reports_corruption_without_repairing_it(tmp_path):
    backup = make_multi_audit_backup(tmp_path, count=2)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("DELETE FROM command_idempotency_reconciliation WHERE sequence=1")
    with managed_sqlite_connection(backup) as conn:
        before = conn.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation").fetchone()[0]
    findings = CommandIdempotencyStore.validate_backup(backup)
    with managed_sqlite_connection(backup) as conn:
        after = conn.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation").fetchone()[0]
    assert any("sequence gap" in finding for finding in findings)
    assert before == after == 1
