import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_completed_reconciliation_audit_survives_database_reopen(tmp_path):
    database = tmp_path / 'ledger.sqlite3'
    store = CommandIdempotencyStore(database)
    store.claim('key-365', 'charge', {'amount': 365}, execution_id='exec-365')
    store.mark_unknown('key-365', 'provider timeout')
    expected = store.reconcile_completed('key-365', {'accepted': True}, evidence='provider receipt 365', execution_id='exec-365')
    store.close()
    reopened = CommandIdempotencyStore(database)
    try:
        assert reopened.get('key-365') == expected
        row = reopened._connection.execute('SELECT evidence, decision FROM command_idempotency_reconciliation WHERE idempotency_key=?', ('key-365',)).fetchone()
        assert tuple(row) == ('provider receipt 365', 'completed')
    finally:
        reopened.close()
