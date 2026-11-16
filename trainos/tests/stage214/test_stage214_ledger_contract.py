from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_payload_key_order_does_not_change_claim_fingerprint(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-214", "move", {"x": 1, "y": 2}, execution_id="exec-214")
        second = store.claim("key-214", "move", {"y": 2, "x": 1}, execution_id="exec-214")
        assert first.created is True
        assert second.created is False
        assert second.record.fingerprint == first.record.fingerprint
    finally:
        store.close()
