import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
def test_corrupt_fingerprint_is_rejected_on_read(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-327', 'move', {'x': 1}, execution_id='exec-327')
        store._connection.execute('UPDATE command_idempotency SET fingerprint=? WHERE idempotency_key=?', ('not-a-valid-fingerprint', 'key-327'))
        store._connection.commit()
        with pytest.raises(RuntimeError, match='corrupt command idempotency fingerprint'):
            store.get('key-327')
    finally: store.close()
