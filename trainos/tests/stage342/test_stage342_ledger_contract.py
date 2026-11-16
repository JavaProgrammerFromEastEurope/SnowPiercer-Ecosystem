from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_completed_command_cannot_be_dispatched_again(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-342", "charge", {"amount": 342}, execution_id="exec-342")
        store.reserve_dispatch("key-342")
        store.complete("key-342", {"accepted": True}, execution_id="exec-342")
        assert store.reserve_dispatch("key-342") is False
        record = store.get("key-342")
        assert record.status.value == "completed"
        assert record.dispatch_generation == 1
    finally:
        store.close()
