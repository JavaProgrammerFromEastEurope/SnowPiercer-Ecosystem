import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_repeated_not_executed_reconciliation_does_not_duplicate_audit(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-362', 'charge', {'amount': 362}, execution_id='exec-362')
        store.reserve_dispatch('key-362')
        store.mark_unknown('key-362', 'provider timeout')
        first = store.reconcile_not_executed('key-362', evidence='provider confirms no operation', execution_id='exec-362')
        count1 = store._connection.execute('SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?', ('key-362',)).fetchone()[0]
        second = store.reconcile_not_executed('key-362', evidence='provider confirms no operation', execution_id='exec-362')
        count2 = store._connection.execute('SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?', ('key-362',)).fetchone()[0]
        assert second == first
        assert count1 == count2 == 1
    finally:
        store.close()
