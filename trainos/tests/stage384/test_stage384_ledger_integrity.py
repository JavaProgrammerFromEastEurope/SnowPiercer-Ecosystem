from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_orphan_reconciliation_audit_is_reported(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("k384", "charge", {"amount": 384})
        store._ensure_reconciliation_table()
        store._connection.execute(
            "INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,decision,dispatch_generation) "
            "VALUES ('missing-key','provider evidence','completed',0)"
        )
        assert any("orphan idempotency key" in item for item in store.check_integrity())
    finally:
        store.close()
