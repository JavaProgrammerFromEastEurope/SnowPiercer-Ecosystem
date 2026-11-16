import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_not_executed_evidence_is_rejected_without_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-363', 'charge', {'amount': 363}, execution_id='exec-363')
        store.reserve_dispatch('key-363')
        store.mark_unknown('key-363', 'provider timeout')
        original = store.reconcile_not_executed('key-363', evidence='evidence A', execution_id='exec-363')
        with pytest.raises(IdempotencyConflict):
            store.reconcile_not_executed('key-363', evidence='evidence B', execution_id='exec-363')
        assert store.get('key-363') == original
        assert store._connection.execute('SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?', ('key-363',)).fetchone()[0] == 1
    finally:
        store.close()
