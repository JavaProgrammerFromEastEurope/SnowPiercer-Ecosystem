from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_version_one_marker_matches_required_structure(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "schema.sqlite3")
    try:
        assert store._connection.execute("PRAGMA user_version").fetchone()[0] == 1
        columns = {row["name"] for row in store._connection.execute("PRAGMA table_info(command_idempotency)")}
        assert {"idempotency_key", "command_name", "fingerprint", "status", "execution_id", "dispatch_started", "dispatch_generation"} <= columns
    finally: store.close()
