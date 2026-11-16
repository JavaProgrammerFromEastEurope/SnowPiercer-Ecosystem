from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_state_and_reason_survive_reopen(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("key-296", "move", {"x": 1}, execution_id="exec-296")
    store.reserve_dispatch("key-296")
    expected = store.mark_unknown("key-296", "ack timeout persisted")
    store.close()
    reopened = CommandIdempotencyStore(path)
    try:
        actual = reopened.get("key-296")
        assert actual == expected
        assert actual.status is IdempotencyStatus.UNKNOWN
        assert actual.uncertainty_reason == "ack timeout persisted"
        assert actual.dispatch_started is True
        assert actual.dispatch_generation == 1
        assert reopened.reserve_dispatch("key-296") is False
    finally:
        reopened.close()
