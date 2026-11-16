import hashlib
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_valid_backup_validation_does_not_change_file_bytes(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    before = hashlib.sha256(backup.read_bytes()).hexdigest()
    assert CommandIdempotencyStore.validate_backup(backup) == ()
    after = hashlib.sha256(backup.read_bytes()).hexdigest()
    assert before == after
