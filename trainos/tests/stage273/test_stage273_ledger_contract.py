from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_duplicate_completion_with_equivalent_json_is_idempotent(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-273", "move", {"x": 1}, execution_id="exec-273")
        first = store.complete("key-273", {"ok": True, "meta": {"b": 2, "a": 1}}, execution_id="exec-273")
        second = store.complete("key-273", {"meta": {"a": 1, "b": 2}, "ok": True}, execution_id="exec-273")
        assert first.status is IdempotencyStatus.COMPLETED
        assert second == first
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        store.close()
