from contextlib import closing
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_duplicate_audit_event_identity_is_rejected(tmp_path):
    backup=make_two_generation_backup(tmp_path)
    with closing(sqlite3.connect(backup)) as conn, conn:
        conn.execute("INSERT INTO command_idempotency_reconciliation (sequence,idempotency_key,evidence,recorded_at,decision,dispatch_generation) SELECT 3,idempotency_key,evidence,recorded_at,decision,dispatch_generation FROM command_idempotency_reconciliation WHERE sequence=2")
    findings=CommandIdempotencyStore.validate_backup(backup)
    assert any("duplicate reconciliation event" in item for item in findings)
