from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_dispatch_requires_bound_execution_identity(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-313", "move", {"x": 1})
        before = store.get("key-313")
        assert store.reserve_dispatch("key-313") is False
        assert store.get("key-313") == before
    finally:
        store.close()
