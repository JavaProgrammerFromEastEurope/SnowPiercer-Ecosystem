from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_global_sequence_remains_contiguous_across_multiple_keys(tmp_path):
    backup = make_multi_audit_backup(tmp_path, count=5)
    assert CommandIdempotencyStore.validate_backup(backup) == ()
