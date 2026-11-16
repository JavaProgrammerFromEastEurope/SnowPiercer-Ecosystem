import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_operation_leaves_source_record_unchanged(tmp_path):
    source = tmp_path / "source.sqlite3"; backup = tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    store.claim("k406", "charge", {"amount": 406})
    before = tuple(store._connection.execute("SELECT idempotency_key, fingerprint, status, result_json, dispatch_generation FROM command_idempotency WHERE idempotency_key='k406'").fetchone())
    destination = sqlite3.connect(backup)
    try: store._connection.backup(destination)
    finally: destination.close()
    after = tuple(store._connection.execute("SELECT idempotency_key, fingerprint, status, result_json, dispatch_generation FROM command_idempotency WHERE idempotency_key='k406'").fetchone())
    try:
        assert before == after
        assert store.check_integrity() == ()
    finally: store.close()
