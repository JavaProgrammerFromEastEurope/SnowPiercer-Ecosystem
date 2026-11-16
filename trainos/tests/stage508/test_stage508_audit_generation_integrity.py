from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_duplicate_sequence_identity_is_reported_even_without_primary_key(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("ALTER TABLE command_idempotency_reconciliation RENAME TO old_audit")
        conn.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER, idempotency_key TEXT NOT NULL, evidence TEXT NOT NULL, recorded_at TEXT NOT NULL, decision TEXT NOT NULL, dispatch_generation INTEGER NOT NULL)")
        conn.execute("INSERT INTO command_idempotency_reconciliation SELECT * FROM old_audit")
        conn.execute("INSERT INTO command_idempotency_reconciliation SELECT sequence, idempotency_key, evidence || ' duplicate', recorded_at, decision, dispatch_generation FROM old_audit WHERE sequence=1")
        conn.execute("DROP TABLE old_audit")
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("sequence must be the primary key" in item for item in findings)
    assert any("invalid or non-monotonic sequence" in item for item in findings)
