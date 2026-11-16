from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_duplicate_execution_bindings_are_reported_after_index_loss(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("k383a", "charge", {"amount": 383}, execution_id="e383a")
        store.claim("k383b", "charge", {"amount": 384}, execution_id="e383b")
        store._connection.execute("DROP INDEX idx_command_idempotency_execution_id")
        store._connection.execute(
            "UPDATE command_idempotency SET execution_id='shared' WHERE idempotency_key IN ('k383a','k383b')"
        )
        assert any("bound to multiple records" in item for item in store.check_integrity())
    finally:
        store.close()
