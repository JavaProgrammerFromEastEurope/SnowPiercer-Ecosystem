from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_rejects_conflicting_decisions_for_same_generation(tmp_path):
    backup = make_multi_audit_backup(tmp_path, count=1)
    with managed_sqlite_connection(backup) as conn:
        row = conn.execute("SELECT idempotency_key, evidence, recorded_at, dispatch_generation FROM command_idempotency_reconciliation WHERE sequence=1").fetchone()
        conn.execute("INSERT INTO command_idempotency_reconciliation(sequence,idempotency_key,evidence,recorded_at,decision,dispatch_generation) VALUES(2,?,?,?,?,?)", (row[0], "independent not-executed evidence", row[2], "not_executed", row[3]))
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("conflicting reconciliation decisions" in finding for finding in findings)
