from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_reopening_does_not_change_schema_version_or_record(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("k399", "charge", {"amount": 399})
    store.close()
    reopened = CommandIdempotencyStore(path)
    try:
        assert reopened._connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert reopened.get("k399").command_name == "charge"
        assert reopened.check_integrity() == ()
    finally:
        reopened.close()
