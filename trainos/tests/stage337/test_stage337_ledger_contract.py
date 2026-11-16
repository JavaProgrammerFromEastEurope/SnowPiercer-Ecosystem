from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_completed_record_survives_database_reopen(tmp_path):
    database = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(database)
    try:
        store.claim("key-337", "charge", {"amount": 100}, execution_id="exec-337")
        completed = store.complete(
            "key-337", {"accepted": True, "provider_reference": "sandbox-337"}, execution_id="exec-337"
        )
        assert completed.status is IdempotencyStatus.COMPLETED
    finally:
        store.close()

    reopened = CommandIdempotencyStore(database)
    try:
        persisted = reopened.get("key-337")
        assert persisted == completed
        assert persisted.result == {"accepted": True, "provider_reference": "sandbox-337"}
    finally:
        reopened.close()
