from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_full_lifecycle_preserves_generation_history_and_terminal_audit(tmp_path):
    path = tmp_path / "lifecycle.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        store.claim("key-187", "set_route", {"route": "R-187"}, execution_id="exec-187")
        assert store.reserve_dispatch("key-187") is True
        store.mark_unknown("key-187", "ack 1 missing")
        store.reconcile_not_executed("key-187", evidence="generation 1 not accepted", execution_id="exec-187")
        assert store.reserve_dispatch("key-187") is True
        store.mark_unknown("key-187", "ack 2 missing")
        completed = store.reconcile_completed("key-187", {"route": "R-187", "ok": True}, evidence="generation 2 completed", execution_id="exec-187")
        assert completed.status is IdempotencyStatus.COMPLETED
        assert completed.dispatch_generation == 2
        rows = store._connection.execute("SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key='key-187' ORDER BY sequence").fetchall()
        assert [tuple(r) for r in rows] == [("generation 1 not accepted", "not_executed", 1), ("generation 2 completed", "completed", 2)]
    finally:
        store.close()
