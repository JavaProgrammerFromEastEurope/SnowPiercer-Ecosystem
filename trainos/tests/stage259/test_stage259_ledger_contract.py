from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_identity_whitespace_is_normalized_before_lookup(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim(" key-259 ", " move ", {"x": 1})
        second = store.claim("key-259", "move", {"x": 1})
        assert first.created is True
        assert second.created is False
        assert second.record.idempotency_key == "key-259"
    finally:
        store.close()
