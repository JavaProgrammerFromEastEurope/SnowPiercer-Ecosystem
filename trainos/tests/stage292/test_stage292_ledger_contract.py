from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_equivalent_completion_json_is_idempotent(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-292", "move", {"x": 1}, execution_id="exec-292")
        first = store.complete("key-292", {"ok": True, "meta": {"a": 1, "b": 2}}, execution_id="exec-292")
        repeated = store.complete("key-292", {"meta": {"b": 2, "a": 1}, "ok": True}, execution_id="exec-292")
        assert repeated == first
        assert repeated.status is IdempotencyStatus.COMPLETED
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        store.close()
