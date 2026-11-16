"""Regression contract: backup validation must release its read-only connection."""
import sqlite3
from unittest.mock import patch
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_validate_backup_closes_read_only_connection(tmp_path):
    source = tmp_path / "ledger.sqlite"
    store = CommandIdempotencyStore(source)
    try:
        store.claim("v84", "probe", {"v": 84})
        backup = tmp_path / "backup.sqlite"
        store.backup_to(backup)
    finally:
        store.close()
    real_connect = sqlite3.connect
    opened = []
    class ConnectionProxy:
        def __init__(self, inner): self.inner = inner; self.closed = False
        def close(self): self.closed = True; return self.inner.close()
        @property
        def row_factory(self): return self.inner.row_factory
        @row_factory.setter
        def row_factory(self, value): self.inner.row_factory = value
        def __getattr__(self, name): return getattr(self.inner, name)
    def tracking_connect(*args, **kwargs):
        proxy = ConnectionProxy(real_connect(*args, **kwargs))
        opened.append(proxy)
        return proxy
    with patch("kernel.command.execution.command_idempotency_store.sqlite3.connect", side_effect=tracking_connect):
        assert CommandIdempotencyStore.validate_backup(backup) == ()
    assert len(opened) == 1
    assert opened[0].closed
