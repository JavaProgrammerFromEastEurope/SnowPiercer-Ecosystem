from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_reopen_preserves_audit_validation_result(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    before = CommandIdempotencyStore.validate_backup(backup)
    store = CommandIdempotencyStore(backup)
    store.close()
    after = CommandIdempotencyStore.validate_backup(backup)
    assert before == after == ()
