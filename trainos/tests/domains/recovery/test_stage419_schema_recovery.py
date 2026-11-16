import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_to_rejects_source_path(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        try:
            store.backup_to(path)
        except ValueError as exc:
            assert "differ from source" in str(exc)
        else:
            raise AssertionError("same-path backup must be rejected")
        assert store.check_integrity() == ()
    finally: store.close()
