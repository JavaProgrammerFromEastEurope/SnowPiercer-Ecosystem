from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_backup_rejects_not_executed_evidence_reused_after_new_dispatch(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    with managed_sqlite_connection(backup) as conn:
        first = conn.execute(
            "SELECT evidence FROM command_idempotency_reconciliation WHERE sequence=1"
        ).fetchone()[0]
        conn.execute(
            "UPDATE command_idempotency_reconciliation SET evidence=? WHERE sequence=2", (first,)
        )
    findings = CommandIdempotencyStore.validate_backup(backup)
    assert any("evidence was reused after a later dispatch generation" in finding for finding in findings)
