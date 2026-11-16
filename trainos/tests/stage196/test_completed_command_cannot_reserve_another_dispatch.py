from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_completed_command_cannot_reserve_another_dispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "s.sqlite3")
    try:
        store.claim("key-196", "move", {"x": 1}, execution_id="exec-196")
        assert store.reserve_dispatch("key-196") is True
        store.complete("key-196", {"ok": True}, execution_id="exec-196")
        assert store.reserve_dispatch("key-196") is False
        assert store.get("key-196").dispatch_generation == 1
    finally:
        store.close()
