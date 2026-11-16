from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_dispatched_record_without_any_audit_is_rejected(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("DELETE FROM command_idempotency_reconciliation")
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("missing reconciliation history" in item for item in findings)
