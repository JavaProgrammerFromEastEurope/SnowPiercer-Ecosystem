from concurrent.futures import ThreadPoolExecutor
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_concurrent_same_key_claim_has_exactly_one_creator(tmp_path):
    path = tmp_path / "shared.sqlite3"
    stores = [CommandIdempotencyStore(path) for _ in range(4)]
    try:
        def claim(i):
            return stores[i].claim("one-key", "reserve", {"amount": 42}).created
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(claim, range(4)))
        assert sum(results) == 1
        assert all(store.get("one-key") is not None for store in stores)
    finally:
        for store in stores: store.close()
