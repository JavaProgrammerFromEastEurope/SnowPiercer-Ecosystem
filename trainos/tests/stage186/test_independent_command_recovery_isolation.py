from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_recovery_of_one_command_does_not_mutate_another(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "isolation.sqlite3")
    try:
        store.claim("key-186-a", "move", {"x": 1}, execution_id="exec-186-a")
        store.reserve_dispatch("key-186-a")
        store.mark_unknown("key-186-a", "lost ack A")
        store.claim("key-186-b", "inspect", {"x": 2}, execution_id="exec-186-b")
        before = store.get("key-186-b")
        store.reconcile_not_executed("key-186-a", evidence="receipt A", execution_id="exec-186-a")
        after = store.get("key-186-b")
        assert before == after
        assert after.dispatch_generation == 0
        assert after.dispatch_started is False
        assert store.count_execution_bindings("exec-186-a") == 1
        assert store.count_execution_bindings("exec-186-b") == 1
    finally:
        store.close()
