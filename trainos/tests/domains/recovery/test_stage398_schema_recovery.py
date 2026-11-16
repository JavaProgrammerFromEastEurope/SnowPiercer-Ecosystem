from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_schema_version_is_recorded(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        assert store._connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert store.check_integrity() == ()
    finally:
        store.close()
