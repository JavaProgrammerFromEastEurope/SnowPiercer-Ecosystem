from concurrent.futures import ThreadPoolExecutor
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_dispatch_reservation_is_single_winner_across_store_instances(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    first = CommandIdempotencyStore(path)
    second = CommandIdempotencyStore(path)
    try:
        first.claim("key-207", "move", {"x": 1}, execution_id="exec-207")
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda store: store.reserve_dispatch("key-207"), (first, second)))
        assert sorted(outcomes) == [False, True]
        record = first.get("key-207")
        assert record.dispatch_started is True
        assert record.dispatch_generation == 1
    finally:
        first.close()
        second.close()
