from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_dispatch_gate_stays_closed_for_completed_and_unknown_records(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "dispatch-gate.sqlite3")
    try:
        store.claim("completed-key", "move", {"x": 1}, execution_id="exec-183-a")
        assert store.reserve_dispatch("completed-key") is True
        store.complete("completed-key", {"done": True}, execution_id="exec-183-a")
        assert store.reserve_dispatch("completed-key") is False
        store.claim("unknown-key", "move", {"x": 2}, execution_id="exec-183-b")
        assert store.reserve_dispatch("unknown-key") is True
        store.mark_unknown("unknown-key", "lost acknowledgement")
        assert store.reserve_dispatch("unknown-key") is False
        assert store.get("completed-key").dispatch_generation == 1
        assert store.get("unknown-key").dispatch_generation == 1
    finally:
        store.close()
