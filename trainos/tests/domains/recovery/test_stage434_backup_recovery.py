import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_backup_rejects_missing_parent_directory(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "source.sqlite3")
    try:
        with pytest.raises(ValueError, match="parent directory must exist"):
            store.backup_to(tmp_path / "absent" / "backup.sqlite3")
        assert not (tmp_path / "absent").exists()
    finally:
        store.close()
