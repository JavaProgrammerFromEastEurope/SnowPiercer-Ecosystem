from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_command_cannot_reserve_another_dispatch(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-246", "move", {"x": 1}, execution_id="exec-246")
        assert store.reserve_dispatch("key-246") is True
        completed = store.complete("key-246", {"ok": True}, execution_id="exec-246")
        assert store.reserve_dispatch("key-246") is False
        assert store.get("key-246") == completed
        assert store.get("key-246").status is IdempotencyStatus.COMPLETED
        assert store.get("key-246").dispatch_generation == 1
    finally:
        store.close()
