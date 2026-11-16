from contextlib import closing
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_timezone_naive_timestamp_is_rejected(tmp_path):
    backup=make_two_generation_backup(tmp_path)
    with closing(sqlite3.connect(backup)) as conn, conn:
        conn.execute("UPDATE command_idempotency_reconciliation SET recorded_at='2026-10-28T12:00:00' WHERE sequence=1")
    findings=CommandIdempotencyStore.validate_backup(backup)
    assert any("timestamp must include timezone" in item for item in findings)
