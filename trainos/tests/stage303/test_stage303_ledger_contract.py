from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_unknown_command_cannot_reserve_dispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-303", "move", {"x": 1}, execution_id="exec-303")
        store.mark_unknown("key-303", "ack timeout")
        before = store.get("key-303")
        assert store.reserve_dispatch("key-303") is False
        assert store.get("key-303") == before
    finally:
        store.close()
