from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_completed_command_cannot_reserve_dispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-304", "move", {"x": 1}, execution_id="exec-304")
        store.complete("key-304", {"ok": True}, execution_id="exec-304")
        before = store.get("key-304")
        assert store.reserve_dispatch("key-304") is False
        assert store.get("key-304") == before
    finally:
        store.close()
