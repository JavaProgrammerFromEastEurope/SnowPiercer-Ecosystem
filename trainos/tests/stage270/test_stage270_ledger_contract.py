from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_nested_payload_key_order_is_canonical_for_claims(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-270", "move", {"outer": {"b": 2, "a": 1}, "items": [1, 2]})
        second = store.claim("key-270", "move", {"items": [1, 2], "outer": {"a": 1, "b": 2}})
        assert first.created is True
        assert second.created is False
        assert second.record.fingerprint == first.record.fingerprint
    finally:
        store.close()
