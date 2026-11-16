from concurrent.futures import ThreadPoolExecutor
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_concurrent_backups_to_distinct_destinations_are_valid(tmp_path):
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("k", "charge", {"cents": 10})
    destinations = [tmp_path / "a.db", tmp_path / "b.db"]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(store.backup_to, destinations))
        assert set(results) == {str(p.resolve()) for p in destinations}
        assert all(CommandIdempotencyStore.validate_backup(p) == () for p in destinations)
    finally:
        store.close()
