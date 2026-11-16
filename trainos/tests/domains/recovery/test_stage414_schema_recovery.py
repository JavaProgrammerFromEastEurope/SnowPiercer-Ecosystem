import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_schema_v1_reopen_keeps_version_and_index_shape(tmp_path):
    path = tmp_path / "stable.sqlite3"
    first = CommandIdempotencyStore(path); first.close()
    before = sqlite3.connect(path)
    columns_before = [tuple(r) for r in before.execute("PRAGMA table_info(command_idempotency)")]
    indexes_before = [tuple(r) for r in before.execute("PRAGMA index_list(command_idempotency)")]
    before.close()
    second = CommandIdempotencyStore(path)
    try:
        assert second._connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert [tuple(r) for r in second._connection.execute("PRAGMA table_info(command_idempotency)")] == columns_before
        assert [tuple(r) for r in second._connection.execute("PRAGMA index_list(command_idempotency)")] == indexes_before
    finally: second.close()
