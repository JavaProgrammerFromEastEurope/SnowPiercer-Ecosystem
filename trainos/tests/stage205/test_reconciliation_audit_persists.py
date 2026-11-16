import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_reconcile_completed_persists_evidence_and_generation(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        store.claim("key-205", "move", {"x": 1}, execution_id="exec-205")
        store.reserve_dispatch("key-205")
        store.mark_unknown("key-205", "ack timeout")
        result = store.reconcile_completed("key-205", {"ok": True}, evidence="signed-provider-record-205", execution_id="exec-205")
        assert result.status is IdempotencyStatus.COMPLETED
        assert result.result == {"ok": True}
        row = store._connection.execute("SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=? ORDER BY sequence DESC LIMIT 1", ("key-205",)).fetchone()
        assert tuple(row) == ("signed-provider-record-205", "completed", 1)
    finally:
        store.close()
