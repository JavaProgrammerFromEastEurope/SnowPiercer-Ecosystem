from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_unbound_claim_cannot_reserve_dispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        claim = store.claim("key-268", "move", {"x": 1})
        assert claim.created is True
        assert store.reserve_dispatch("key-268") is False
        record = store.get("key-268")
        assert record is not None
        assert record.dispatch_started is False
        assert record.dispatch_generation == 0
    finally:
        store.close()
