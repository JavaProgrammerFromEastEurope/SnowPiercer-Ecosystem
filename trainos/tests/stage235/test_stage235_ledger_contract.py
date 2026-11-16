from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_dispatch_reservation_and_unknown_state_survive_store_reopen(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(db)
    store.claim("key-235", "move", {"x": 1}, execution_id="exec-235")
    assert store.reserve_dispatch("key-235") is True
    store.mark_unknown("key-235", "process stopped after dispatch")
    store.close()

    reopened = CommandIdempotencyStore(db)
    try:
        record = reopened.get("key-235")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.dispatch_started is True
        assert record.dispatch_generation == 1
        assert reopened.reserve_dispatch("key-235") is False
    finally:
        reopened.close()
