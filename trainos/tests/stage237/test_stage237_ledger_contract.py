from concurrent.futures import ThreadPoolExecutor
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_two_store_instances_cannot_both_reserve_same_dispatch(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    setup = CommandIdempotencyStore(db)
    setup.claim("key-237", "move", {"x": 1}, execution_id="exec-237")
    setup.close()
    first = CommandIdempotencyStore(db)
    second = CommandIdempotencyStore(db)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda store: store.reserve_dispatch("key-237"), (first, second)))
        assert sorted(results) == [False, True]
        record = first.get("key-237")
        assert record.dispatch_started is True
        assert record.dispatch_generation == 1
    finally:
        first.close()
        second.close()
