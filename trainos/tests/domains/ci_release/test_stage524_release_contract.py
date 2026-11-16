from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_multiple_keys_have_independent_valid_audit_histories(tmp_path):
    backup=make_multi_audit_backup(tmp_path,count=4)
    assert CommandIdempotencyStore.validate_backup(backup)==()
