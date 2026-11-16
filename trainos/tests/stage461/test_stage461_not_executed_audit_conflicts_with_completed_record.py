import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_not_executed_audit_cannot_conflict_with_completed_record(tmp_path):
    db = tmp_path / "ledger.db"
    store = CommandIdempotencyStore(db)
    store.claim("k", "charge", {"cents": 10})
    store.mark_unknown("k", reason="timeout")
    store.reconcile_completed("k", {"ok": True}, evidence="provider-confirmed")
    store.close()
    con = sqlite3.connect(db)
    con.execute("UPDATE command_idempotency_reconciliation SET decision='not_executed'")
    con.commit(); con.close()
    findings = CommandIdempotencyStore.validate_backup(db)
    assert any("not_executed decision conflicts with completed record" in item for item in findings)
