from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_never_dispatched_record_does_not_require_reconciliation_history(tmp_path):
    source=tmp_path/'source.db'; backup=tmp_path/'backup.db'
    store=CommandIdempotencyStore(source)
    store.claim('never-dispatched','charge',{'cents':100})
    store.backup_to(backup); store.close()
    assert CommandIdempotencyStore.validate_backup(backup)==()
