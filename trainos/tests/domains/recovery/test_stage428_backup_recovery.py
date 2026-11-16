import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_valid_backup_passes_read_only_validation(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    try:
        store.claim("valid", "record", {"n": 1})
        store.backup_to(backup)
        assert CommandIdempotencyStore.validate_backup(backup) == ()
    finally:
        store.close()
