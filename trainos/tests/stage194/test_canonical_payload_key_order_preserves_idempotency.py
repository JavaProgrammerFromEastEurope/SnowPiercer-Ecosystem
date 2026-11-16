from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_canonical_payload_key_order_preserves_idempotency(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "s.sqlite3")
    try:
        first = store.claim("key-194", "move", {"a": 1, "b": 2}, execution_id="exec-194")
        second = store.claim("key-194", "move", {"b": 2, "a": 1}, execution_id="exec-194")
        assert first.created is True
        assert second.created is False
        assert first.record.fingerprint == second.record.fingerprint
    finally:
        store.close()
