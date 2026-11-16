from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_backup_rejects_per_key_dispatch_generation_regression(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("UPDATE command_idempotency_reconciliation SET dispatch_generation=2 WHERE sequence=1")
        conn.execute("UPDATE command_idempotency_reconciliation SET dispatch_generation=1 WHERE sequence=2")
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("dispatch generation regresses" in finding for finding in findings)
