import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_keeps_unknown_state_without_authorizing_retry(tmp_path):
    source = tmp_path / "source.sqlite3"; backup = tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    store.claim("k405", "charge", {"amount": 405}, execution_id="exec405")
    store.reserve_dispatch("k405"); store.mark_unknown("k405", "ack lost")
    destination = sqlite3.connect(backup)
    try: store._connection.backup(destination)
    finally: destination.close(); store.close()
    restored = CommandIdempotencyStore(backup)
    try:
        record = restored.get("k405")
        assert record.status.value == "unknown" and record.uncertainty_reason == "ack lost"
        assert record.dispatch_started and record.dispatch_generation == 1
        assert restored.reserve_dispatch("k405") is False
    finally: restored.close()
