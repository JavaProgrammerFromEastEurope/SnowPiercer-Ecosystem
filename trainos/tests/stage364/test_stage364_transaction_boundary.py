import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_reconciliation_wrong_execution_id_rolls_back_all_changes(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-364', 'charge', {'amount': 364}, execution_id='exec-364')
        store.mark_unknown('key-364', 'provider timeout')
        original = store.get('key-364')
        with pytest.raises(IdempotencyConflict):
            store.reconcile_completed('key-364', {'accepted': True}, evidence='receipt', execution_id='wrong-exec')
        assert store.get('key-364') == original
        table = store._connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()
        assert table is None
    finally:
        store.close()
