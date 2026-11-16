from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_dispatch_reservation_is_single_and_generation_is_stable(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        store.claim("key-266", "move", {"x": 1}, execution_id="exec-266")
        assert store.reserve_dispatch("key-266") is True
        assert store.reserve_dispatch("key-266") is False
        assert store.get("key-266").dispatch_generation == 1
    finally:
        store.close()
    reopened = CommandIdempotencyStore(path)
    try:
        assert reopened.get("key-266").dispatch_started is True
        assert reopened.get("key-266").dispatch_generation == 1
        assert reopened.reserve_dispatch("key-266") is False
    finally:
        reopened.close()
