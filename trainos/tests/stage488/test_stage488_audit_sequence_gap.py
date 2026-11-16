from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_backup_rejects_gap_in_global_audit_sequence(tmp_path):
    backup = make_multi_audit_backup(tmp_path, count=3)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("DELETE FROM command_idempotency_reconciliation WHERE sequence=2")
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("sequence gap" in finding for finding in findings)
