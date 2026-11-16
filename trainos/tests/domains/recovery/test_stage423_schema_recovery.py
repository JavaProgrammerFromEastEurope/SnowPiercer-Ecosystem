import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_garbage_backup_is_rejected_without_becoming_a_store(tmp_path):
    path = tmp_path / "damaged.sqlite3"
    path.write_bytes(b"not a sqlite database")
    with pytest.raises(sqlite3.DatabaseError):
        CommandIdempotencyStore(path)
