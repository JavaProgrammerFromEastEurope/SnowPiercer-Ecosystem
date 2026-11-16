import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_backup_does_not_overwrite_existing_destination(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    backup.write_bytes(b"preserve this file")
    try:
        with pytest.raises(FileExistsError):
            store.backup_to(backup)
        assert backup.read_bytes() == b"preserve this file"
    finally:
        store.close()
