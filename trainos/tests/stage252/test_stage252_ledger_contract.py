import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_not_executed_evidence_is_rejected_without_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-252", "move", {"x": 1}, execution_id="exec-252")
        store.reserve_dispatch("key-252")
        store.mark_unknown("key-252", "ack timeout")
        store.reconcile_not_executed("key-252", evidence="proof-A-252", execution_id="exec-252")
        before = store.get("key-252")
        with pytest.raises(IdempotencyConflict, match="conflicting evidence"):
            store.reconcile_not_executed("key-252", evidence="proof-B-252", execution_id="exec-252")
        assert store.get("key-252") == before
        rows = store._connection.execute("SELECT evidence FROM command_idempotency_reconciliation ORDER BY sequence").fetchall()
        assert [row[0] for row in rows] == ["proof-A-252"]
    finally:
        store.close()
