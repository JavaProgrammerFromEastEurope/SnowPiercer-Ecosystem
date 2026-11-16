from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_malformed_fingerprint_is_reported(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("k381", "charge", {"amount": 381})
        store._connection.execute(
            "UPDATE command_idempotency SET fingerprint='bad' WHERE idempotency_key='k381'"
        )
        assert any("corrupt command idempotency fingerprint" in item for item in store.check_integrity())
    finally:
        store.close()
