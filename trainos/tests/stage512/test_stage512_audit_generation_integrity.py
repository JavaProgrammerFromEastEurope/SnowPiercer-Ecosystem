import shutil
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_verified_copy_retains_latest_generation_invariant(tmp_path):
    source = make_two_generation_backup(tmp_path)
    copied = tmp_path / "copied.db"
    shutil.copy2(source, copied)
    assert CommandIdempotencyStore.validate_backup(source) == ()
    assert CommandIdempotencyStore.validate_backup(copied) == ()
