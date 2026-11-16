from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_backup_accepts_increasing_generations_with_distinct_evidence(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    assert CommandIdempotencyStore.validate_backup(backup) == ()
