from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_end_to_end_validation_refuses_missing_latest_audit_without_repair(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("DELETE FROM command_idempotency_reconciliation WHERE sequence=2")
    before = backup.read_bytes()
    findings = CommandIdempotencyStore.validate_backup(backup)
    after = backup.read_bytes()
    assert any("latest dispatch generation mismatch" in item for item in findings)
    assert before == after
