import shutil
from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_copied_backup_keeps_validated_integrity(tmp_path):
    backup = make_multi_audit_backup(tmp_path, count=2)
    copied = tmp_path / "copied.db"
    shutil.copy2(backup, copied)
    assert CommandIdempotencyStore.validate_backup(copied) == ()
