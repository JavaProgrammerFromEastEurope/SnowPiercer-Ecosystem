from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_integrity_check_does_not_create_optional_audit_table(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        assert store.check_integrity() == ()
        table = store._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'"
        ).fetchone()
        assert table is None
    finally:
        store.close()
