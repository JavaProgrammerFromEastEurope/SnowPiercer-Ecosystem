from contextlib import closing
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_missing_history_findings_are_stable_and_read_only(tmp_path):
    backup=make_two_generation_backup(tmp_path)
    with closing(sqlite3.connect(backup)) as conn, conn:
        conn.execute("DELETE FROM command_idempotency_reconciliation")
    before=backup.read_bytes()
    first=CommandIdempotencyStore.validate_backup(backup)
    second=CommandIdempotencyStore.validate_backup(backup)
    assert first==second
    assert any("missing reconciliation history" in item for item in first)
    assert backup.read_bytes()==before
