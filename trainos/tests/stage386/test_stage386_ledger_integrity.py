from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_audit_generation_ahead_of_record_is_reported(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("k386", "charge", {"amount": 386}, execution_id="e386")
        store.mark_unknown("k386", "timeout")
        store._ensure_reconciliation_table()
        store._connection.execute(
            "INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,decision,dispatch_generation) "
            "VALUES ('k386','provider evidence','not_executed',5)"
        )
        assert any("invalid dispatch generation" in item for item in store.check_integrity())
    finally:
        store.close()
