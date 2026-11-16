import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_duplicate_completion_is_idempotent_but_conflicting_result_is_rejected(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "duplicate-completion.sqlite3")
    try:
        store.claim("key-182", "inspect", {"target": "C"}, execution_id="exec-182")
        store.reserve_dispatch("key-182")
        store.mark_unknown("key-182", "lost ack")
        first = store.reconcile_completed("key-182", {"ok": True, "value": 2}, evidence="receipt-182", execution_id="exec-182")
        second = store.reconcile_completed("key-182", {"value": 2, "ok": True}, evidence="receipt-182-duplicate", execution_id="exec-182")
        assert first.result == second.result == {"ok": True, "value": 2}
        with pytest.raises(IdempotencyConflict, match="conflicting duplicate"):
            store.reconcile_completed("key-182", {"ok": False}, evidence="bad-receipt", execution_id="exec-182")
        assert store.get("key-182").result == {"ok": True, "value": 2}
    finally:
        store.close()
