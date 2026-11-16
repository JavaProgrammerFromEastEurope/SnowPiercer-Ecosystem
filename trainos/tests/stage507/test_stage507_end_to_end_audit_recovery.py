import shutil
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_end_to_end_backup_restore_validation_and_safe_refusal(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    assert CommandIdempotencyStore.validate_backup(backup) == ()
    restored = tmp_path / "restored.db"
    shutil.copy2(backup, restored)
    assert CommandIdempotencyStore.validate_backup(restored) == ()
    store = CommandIdempotencyStore(restored)
    assert store.get("key-1") is not None
    store.close()
    assert CommandIdempotencyStore.validate_backup(restored) == ()
