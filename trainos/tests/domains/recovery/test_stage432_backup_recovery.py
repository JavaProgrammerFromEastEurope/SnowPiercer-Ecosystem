import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_missing_execution_index_fails_validation(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    try:
        store.backup_to(backup)
    finally:
        store.close()
    db = sqlite3.connect(backup)
    db.execute("DROP INDEX idx_command_idempotency_execution_id")
    db.commit()
    db.close()
    assert "schema: execution_id uniqueness index is missing" in CommandIdempotencyStore.validate_backup(backup)
