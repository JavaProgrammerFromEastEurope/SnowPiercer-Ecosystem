from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_concurrent_independent_stores_only_one_dispatch_reservation_wins(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    setup = CommandIdempotencyStore(path)
    setup.claim("key-307", "move", {"x": 1}, execution_id="exec-307")
    setup.close()
    first = CommandIdempotencyStore(path)
    second = CommandIdempotencyStore(path)
    barrier = Barrier(2)
    def reserve(store):
        barrier.wait(timeout=5)
        return store.reserve_dispatch("key-307")
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, (first, second)))
        assert sorted(results) == [False, True]
        record = first.get("key-307")
        assert record.dispatch_started is True
        assert record.dispatch_generation == 1
    finally:
        first.close()
        second.close()
