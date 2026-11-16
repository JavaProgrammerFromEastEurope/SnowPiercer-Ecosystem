from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_invalid_audit_decision_and_empty_evidence_are_reported(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("k385", "charge", {"amount": 385}, execution_id="e385")
        store.mark_unknown("k385", "timeout")
        store._ensure_reconciliation_table()
        store._connection.execute(
            "INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,decision,dispatch_generation) "
            "VALUES ('k385','   ','mystery',0)"
        )
        findings = store.check_integrity()
        assert any("empty evidence" in item for item in findings)
        assert any("invalid decision" in item for item in findings)
    finally:
        store.close()
