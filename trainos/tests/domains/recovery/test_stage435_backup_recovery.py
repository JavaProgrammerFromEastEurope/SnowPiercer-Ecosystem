import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_concurrent_backup_publication_never_overwrites(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "shared-backup.sqlite3"
    stores = [CommandIdempotencyStore(source) for _ in range(3)]
    try:
        for store in stores:
            store.claim("shared", "record", {"same": True})
        def attempt(store):
            try:
                store.backup_to(backup)
                return "published"
            except FileExistsError:
                return "exists"
        with ThreadPoolExecutor(max_workers=3) as pool:
            outcomes = list(pool.map(attempt, stores))
        assert outcomes.count("published") == 1
        assert outcomes.count("exists") == 2
        assert CommandIdempotencyStore.validate_backup(backup) == ()
    finally:
        for store in stores:
            store.close()
