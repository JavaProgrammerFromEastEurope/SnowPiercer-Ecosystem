from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_non_monotonic_timestamps_are_rejected(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("UPDATE command_idempotency_reconciliation SET recorded_at='2000-01-01T00:00:00+00:00' WHERE sequence=2")
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("timestamp precedes an earlier audit event" in item for item in findings)
