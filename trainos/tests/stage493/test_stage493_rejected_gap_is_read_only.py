from tests.sqlite_resource_helpers import managed_sqlite_connection
import hashlib
import sqlite3
from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_gap_validation_does_not_mutate_backup(tmp_path):
    backup = make_multi_audit_backup(tmp_path, count=2)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("DELETE FROM command_idempotency_reconciliation WHERE sequence=1")
    before = hashlib.sha256(backup.read_bytes()).hexdigest()
    findings = CommandIdempotencyStore.validate_backup(backup)
    after = hashlib.sha256(backup.read_bytes()).hexdigest()
    assert findings
    assert before == after
