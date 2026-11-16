from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_end_to_end_backup_audit_validation_and_unknown(tmp_path):
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("k", "charge", {"cents": 10})
    store.mark_unknown("k", reason="provider acknowledgement missing")
    store.reconcile_completed("k", {"provider_ref": "ref-123"}, evidence="provider lookup confirmed completion")
    backup = tmp_path / "backup.db"
    store.backup_to(backup)
    store.close()
    assert CommandIdempotencyStore.validate_backup(backup) == ()
    restored = CommandIdempotencyStore(backup)
    try:
        assert restored.get("k").status is IdempotencyStatus.COMPLETED
        assert restored.get("k").result == {"provider_ref": "ref-123"}
        assert restored.check_integrity() == ()
    finally:
        restored.close()
