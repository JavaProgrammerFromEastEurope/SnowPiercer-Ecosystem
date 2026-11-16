from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_marking_unknown_twice_with_same_reason_is_idempotent(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-242", "move", {"x": 1})
        first = store.mark_unknown("key-242", "ack timeout")
        second = store.mark_unknown("key-242", "ack timeout")
        assert first == second
        assert second.status is IdempotencyStatus.UNKNOWN
        assert second.uncertainty_reason == "ack timeout"
    finally:
        store.close()
