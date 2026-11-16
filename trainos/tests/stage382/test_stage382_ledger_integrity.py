from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_missing_execution_uniqueness_index_is_reported(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("k382", "charge", {"amount": 382}, execution_id="e382")
        store._connection.execute("DROP INDEX idx_command_idempotency_execution_id")
        assert any("execution_id uniqueness index is missing" in item for item in store.check_integrity())
    finally:
        store.close()
