from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_same_completion_is_idempotent(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "s.sqlite3")
    try:
        store.claim("key-191", "move", {"x": 1}, execution_id="exec-191")
        first = store.complete("key-191", {"ok": True, "value": 1}, execution_id="exec-191")
        second = store.complete("key-191", {"value": 1, "ok": True}, execution_id="exec-191")
        assert first.status == second.status
        assert second.result == {"ok": True, "value": 1}
    finally:
        store.close()
