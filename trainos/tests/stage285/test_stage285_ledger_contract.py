from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_completed_result_and_dispatch_generation_survive_reopen(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("key-285", "move", {"x": 1}, execution_id="exec-285")
    assert store.reserve_dispatch("key-285") is True
    completed = store.complete("key-285", {"ok": True, "receipt": "r285"}, execution_id="exec-285")
    store.close()

    reopened = CommandIdempotencyStore(path)
    try:
        restored = reopened.get("key-285")
        assert restored == completed
        assert restored.status is IdempotencyStatus.COMPLETED
        assert restored.result == {"ok": True, "receipt": "r285"}
        assert restored.dispatch_generation == 1
        assert reopened.reserve_dispatch("key-285") is False
    finally:
        reopened.close()
