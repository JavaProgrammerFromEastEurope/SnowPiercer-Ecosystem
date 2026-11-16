from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_state_survives_store_reopen(tmp_path):
    path = tmp_path / "s.sqlite3"
    first = CommandIdempotencyStore(path)
    first.claim("key-195", "move", {"x": 1}, execution_id="exec-195")
    first.complete("key-195", {"ok": True}, execution_id="exec-195")
    first.close()
    second = CommandIdempotencyStore(path)
    try:
        record = second.get("key-195")
        assert record.status is IdempotencyStatus.COMPLETED
        assert record.result == {"ok": True}
        assert record.dispatch_generation == 0
    finally:
        second.close()
