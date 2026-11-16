from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_two_store_instances_cannot_reserve_same_dispatch_twice(tmp_path):
    database = tmp_path / "ledger.sqlite3"
    first = CommandIdempotencyStore(database)
    second = CommandIdempotencyStore(database)
    try:
        first.claim("key-347", "charge", {"amount": 347}, execution_id="exec-347")
        assert first.reserve_dispatch("key-347") is True
        assert second.reserve_dispatch("key-347") is False
        assert first.get("key-347").dispatch_generation == 1
        assert second.get("key-347").dispatch_generation == 1
    finally:
        first.close()
        second.close()
