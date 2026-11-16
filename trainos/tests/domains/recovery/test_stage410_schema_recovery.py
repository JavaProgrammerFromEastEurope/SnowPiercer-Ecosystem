from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_execution_id_index_is_unique_and_partial(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "schema.sqlite3")
    try:
        row = next(r for r in store._connection.execute("PRAGMA index_list(command_idempotency)") if r["name"] == "idx_command_idempotency_execution_id")
        assert row["unique"] == 1
        assert row["partial"] == 1
        columns = store._connection.execute("PRAGMA index_info(idx_command_idempotency_execution_id)").fetchall()
        assert [r["name"] for r in columns] == ["execution_id"]
    finally: store.close()
