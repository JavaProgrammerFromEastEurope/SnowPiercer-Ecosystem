from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_concurrent_same_destination_has_single_winner(tmp_path):
    source = tmp_path / "source.db"
    first = CommandIdempotencyStore(source)
    first.claim("k", "charge", {"cents": 10})
    second = CommandIdempotencyStore(source)
    destination = tmp_path / "shared.db"
    barrier = Barrier(2)
    def publish(store):
        barrier.wait()
        try:
            return ("ok", store.backup_to(destination))
        except FileExistsError:
            return ("exists", None)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, [first, second]))
        assert sum(result[0] == "ok" for result in results) == 1
        assert sum(result[0] == "exists" for result in results) == 1
        assert CommandIdempotencyStore.validate_backup(destination) == ()
        assert list(tmp_path.glob(".shared.db.*.tmp")) == []
    finally:
        first.close()
        second.close()
