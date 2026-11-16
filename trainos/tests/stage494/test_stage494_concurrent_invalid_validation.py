from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_concurrent_validators_consistently_reject_sequence_gap(tmp_path):
    backup = make_multi_audit_backup(tmp_path, count=3)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("DELETE FROM command_idempotency_reconciliation WHERE sequence=2")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(CommandIdempotencyStore.validate_backup, [backup] * 24))
    assert all(any("sequence gap" in finding for finding in result) for result in results)
    assert len({tuple(result) for result in results}) == 1
