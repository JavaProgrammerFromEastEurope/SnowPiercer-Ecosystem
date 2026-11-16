from concurrent.futures import ThreadPoolExecutor
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_concurrent_dispatch_reservation_has_one_winner(tmp_path):
    database = tmp_path / 'ledger.sqlite3'
    setup = CommandIdempotencyStore(database)
    setup.claim('key-366', 'charge', {'amount': 366}, execution_id='exec-366')
    setup.close()
    stores = [CommandIdempotencyStore(database), CommandIdempotencyStore(database)]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda s: s.reserve_dispatch('key-366'), stores))
        assert sorted(results) == [False, True]
        records = [s.get('key-366') for s in stores]
        assert all(r.dispatch_started for r in records)
        assert all(r.dispatch_generation == 1 for r in records)
    finally:
        for store in stores:
            store.close()
