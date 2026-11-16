import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
def test_blank_reconciliation_evidence_does_not_mutate_unknown_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-323', 'move', {'x': 1}, execution_id='exec-323')
        before = store.mark_unknown('key-323', 'ack timeout')
        for evidence in ('', '   '):
            with pytest.raises(ValueError, match='evidence must not be empty'):
                store.reconcile_not_executed('key-323', evidence=evidence, execution_id='exec-323')
            assert store.get('key-323') == before
    finally: store.close()
