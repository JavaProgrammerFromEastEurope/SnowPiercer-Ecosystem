from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_duplicate_event_with_distinct_sequence_is_rejected(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    with managed_sqlite_connection(backup) as conn:
        row = conn.execute("SELECT idempotency_key, evidence, recorded_at, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE sequence=1").fetchone()
        conn.execute("INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence,recorded_at,decision,dispatch_generation) VALUES(?,?,?,?,?)", row)
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("duplicate reconciliation event" in item for item in findings)
