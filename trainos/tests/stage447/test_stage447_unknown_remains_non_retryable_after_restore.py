from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_is_not_retried_after_backup_restore(tmp_path):
    source=tmp_path/'source.db'; backup=tmp_path/'backup.db'
    store=CommandIdempotencyStore(source)
    try:
        store.claim('k','charge',{'cents':500},execution_id='e'); store.reserve_dispatch('k'); store.mark_unknown('k','provider timeout')
        store.backup_to(backup)
    finally: store.close()
    restored=CommandIdempotencyStore(backup)
    try:
        claim=restored.claim('k','charge',{'cents':500})
        assert claim.created is False and claim.record.status is IdempotencyStatus.UNKNOWN
    finally: restored.close()
