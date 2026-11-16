from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_restored_completed_audit_survives_reopen(tmp_path):
    source=tmp_path/'source.db'; backup=tmp_path/'backup.db'
    store=CommandIdempotencyStore(source)
    try:
        store.claim('k','charge',{'cents':500},execution_id='e'); store.reserve_dispatch('k')
        store.mark_unknown('k','timeout'); store.reconcile_completed('k',{'receipt':'r1'},evidence='provider-confirmed',execution_id='e')
        store.backup_to(backup)
    finally: store.close()
    restored=CommandIdempotencyStore(backup)
    try: assert restored.get('k').status is IdempotencyStatus.COMPLETED
    finally: restored.close()
    assert CommandIdempotencyStore.validate_backup(backup)==()
