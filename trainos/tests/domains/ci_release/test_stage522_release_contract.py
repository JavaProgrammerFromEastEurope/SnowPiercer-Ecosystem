from contextlib import closing
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_audit_generation_ahead_of_record_is_rejected(tmp_path):
    backup=make_two_generation_backup(tmp_path)
    with closing(sqlite3.connect(backup)) as conn, conn:
        conn.execute("UPDATE command_idempotency_reconciliation SET dispatch_generation=3 WHERE sequence=2")
    findings=CommandIdempotencyStore.validate_backup(backup)
    assert any("invalid dispatch generation" in item for item in findings)
