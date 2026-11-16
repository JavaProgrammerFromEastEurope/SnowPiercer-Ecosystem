import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_sqlite_file_without_ledger_table_is_rejected(tmp_path):
    backup = tmp_path / "incomplete.sqlite3"
    db = sqlite3.connect(backup)
    db.execute("CREATE TABLE unrelated (value TEXT)")
    db.execute("PRAGMA user_version = 1")
    db.commit()
    db.close()
    assert "schema: command_idempotency table is missing" in CommandIdempotencyStore.validate_backup(backup)


def test_garbage_file_is_reported_as_invalid_backup(tmp_path):
    damaged = tmp_path / "garbage.sqlite3"
    damaged.write_bytes(b"not a SQLite database")
    findings = CommandIdempotencyStore.validate_backup(damaged)
    assert findings and findings[0].startswith("backup: cannot validate SQLite database:")
