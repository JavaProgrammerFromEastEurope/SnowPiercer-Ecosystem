from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_dispatch_reservation_survives_reopen(tmp_path):
    database = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(database)
    store.claim("key-340", "charge", {"amount": 340}, execution_id="exec-340")
    assert store.reserve_dispatch("key-340") is True
    first = store.get("key-340")
    store.close()

    reopened = CommandIdempotencyStore(database)
    try:
        assert reopened.reserve_dispatch("key-340") is False
        persisted = reopened.get("key-340")
        assert persisted.dispatch_started is True
        assert persisted.dispatch_generation == 1
        assert persisted == first
    finally:
        reopened.close()
