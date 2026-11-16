import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_future_schema_version_fails_validation(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    try:
        store.backup_to(backup)
    finally:
        store.close()
    db = sqlite3.connect(backup)
    try:
        db.execute("PRAGMA user_version = 999")
        db.commit()
    finally:
        db.close()
    assert "schema: expected version 1, found 999" in CommandIdempotencyStore.validate_backup(backup)
