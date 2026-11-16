from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_unknown_outcome_requires_explicit_reconciliation_before_reservation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "s.sqlite3")
    try:
        store.claim("key-197", "move", {"x": 1}, execution_id="exec-197")
        assert store.reserve_dispatch("key-197") is True
        store.mark_unknown("key-197", "ack timeout")
        assert store.reserve_dispatch("key-197") is False
        assert store.get("key-197").dispatch_generation == 1
    finally:
        store.close()
