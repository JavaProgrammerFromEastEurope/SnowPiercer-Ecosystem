import sqlite3
from concurrent.futures import ThreadPoolExecutor
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_concurrent_initializers_leave_one_valid_schema(tmp_path):
    path = tmp_path / "shared.sqlite3"
    def initialize(_):
        store = CommandIdempotencyStore(path)
        try:
            assert store.check_integrity() == ()
        finally:
            store.close()
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(initialize, range(6)))
    db = sqlite3.connect(path)
    try:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency'").fetchone()[0] == 1
    finally: db.close()
