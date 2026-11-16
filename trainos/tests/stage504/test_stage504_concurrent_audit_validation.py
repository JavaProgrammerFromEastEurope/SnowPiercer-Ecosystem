from concurrent.futures import ThreadPoolExecutor
from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_concurrent_validators_return_consistent_results(tmp_path):
    backup = make_multi_audit_backup(tmp_path, count=3)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(CommandIdempotencyStore.validate_backup, [backup] * 12))
    assert results == [()] * 12
