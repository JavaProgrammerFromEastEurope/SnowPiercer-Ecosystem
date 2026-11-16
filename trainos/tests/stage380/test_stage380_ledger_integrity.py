from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_invalid_result_json_is_reported_without_rewriting_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("k380", "charge", {"amount": 380}, execution_id="e380")
        store.complete("k380", {"ok": True}, execution_id="e380")
        store._connection.execute(
            "UPDATE command_idempotency SET result_json='not-json' WHERE idempotency_key='k380'"
        )
        before = store._connection.execute(
            "SELECT result_json FROM command_idempotency WHERE idempotency_key='k380'"
        ).fetchone()[0]
        findings = store.check_integrity()
        after = store._connection.execute(
            "SELECT result_json FROM command_idempotency WHERE idempotency_key='k380'"
        ).fetchone()[0]
        assert any("corrupt command idempotency record" in item for item in findings)
        assert before == after == "not-json"
    finally:
        store.close()
