from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_binding_diagnostic_detects_duplicate_after_unique_index_loss(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-297-a", "move", {"x": 1}, execution_id="exec-297")
        store._connection.execute("DROP INDEX idx_command_idempotency_execution_id")
        store._connection.execute(
            "INSERT INTO command_idempotency(idempotency_key, command_name, fingerprint, status, execution_id) "
            "VALUES (?, ?, ?, 'claimed', ?)",
            ("key-297-b", "stop", "a" * 64, "exec-297"),
        )
        assert store.count_execution_bindings("exec-297") == 2
    finally:
        store.close()
