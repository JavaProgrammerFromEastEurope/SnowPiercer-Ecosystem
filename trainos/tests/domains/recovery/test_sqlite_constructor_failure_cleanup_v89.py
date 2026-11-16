"""Constructor-failure connection cleanup contracts for recovery stores."""
import sqlite3
import pytest
from kernel.command.events.event_integrity_anchor_store import EventIntegrityAnchorStore
from kernel.command.events.event_log_recovery_attempt_store import EventLogRecoveryAttemptStore

@pytest.mark.parametrize('store', [EventIntegrityAnchorStore, EventLogRecoveryAttemptStore])
def test_failed_constructor_releases_database(store, tmp_path, monkeypatch):
    real_connect = sqlite3.connect
    connections = []
    class Tracked:
        def __init__(self, conn):
            object.__setattr__(self, 'conn', conn)
            object.__setattr__(self, 'closed', False)
        def __getattr__(self, name):
            return getattr(self.conn, name)
        def __setattr__(self, name, value):
            setattr(self.conn, name, value)
        def __enter__(self):
            self.conn.__enter__()
            return self
        def __exit__(self, *args):
            return self.conn.__exit__(*args)
        def close(self):
            self.conn.close()
            object.__setattr__(self, 'closed', True)
    def connect(*args, **kwargs):
        conn = Tracked(real_connect(*args, **kwargs))
        connections.append(conn)
        return conn
    monkeypatch.setattr(sqlite3, 'connect', connect)
    def explode(*args, **kwargs):
        raise sqlite3.OperationalError('injected schema initialization failure')
    # Force failure after connect, during first SQL operation.
    original_execute = Tracked.__getattr__
    def failing_getattr(self, name):
        if name == 'execute':
            return explode
        return original_execute(self, name)
    monkeypatch.setattr(Tracked, '__getattr__', failing_getattr)
    with pytest.raises(sqlite3.OperationalError, match='injected'):
        store(tmp_path / 'store.sqlite')
    assert len(connections) == 1
    assert connections[0].closed
