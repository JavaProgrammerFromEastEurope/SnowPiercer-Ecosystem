from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_valid_reconciliation_audit_passes_backup_validation(tmp_path):
    source=tmp_path/'source.db'; backup=tmp_path/'backup.db'
    store=CommandIdempotencyStore(source)
    try:
        store.claim('k','charge',{'cents':100},execution_id='e1'); store.reserve_dispatch('k')
        store.mark_unknown('k','timeout'); store.reconcile_completed('k',{'ok':True},evidence='provider-confirmed',execution_id='e1')
        store.backup_to(backup)
    finally: store.close()
    assert CommandIdempotencyStore.validate_backup(backup)==()
