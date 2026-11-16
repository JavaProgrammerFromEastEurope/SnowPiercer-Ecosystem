"""Fencing-token tests for recovery ownership across retries and stale workers."""
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def test_stale_owner_cannot_finish_after_authorized_retry(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    first = journal.begin_attempt("fenced", "first owner")
    assert first.owner_run_id
    assert first.fencing_token == 1
    journal.finish_failure(
        "fenced", "simulated interruption",
        owner_run_id=first.owner_run_id, fencing_token=first.fencing_token,
    )
    journal.authorize_retry("fenced", operator="reviewer", reason="retry reviewed")
    second = journal.begin_attempt("fenced", "replacement owner")
    assert second.owner_run_id and second.owner_run_id != first.owner_run_id
    assert second.fencing_token == first.fencing_token + 1

    with pytest.raises(RecoveryAttemptBlocked, match="stale recovery owner or fencing token"):
        journal.finish_success(
            "fenced", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token,
        )
    state = journal.get("fenced")
    assert state.status is RecoveryAttemptStatus.IN_PROGRESS
    assert state.owner_run_id == second.owner_run_id
    assert state.fencing_token == second.fencing_token

    completed = journal.finish_success(
        "fenced", owner_run_id=second.owner_run_id, fencing_token=second.fencing_token,
    )
    assert completed.status is RecoveryAttemptStatus.SUCCEEDED
    journal.close()


def test_old_journal_schema_migrates_owner_identity_columns(tmp_path):
    database = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(database)
    connection.execute("""
        CREATE TABLE recovery_attempts (
            attempt_key TEXT PRIMARY KEY, status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL CHECK(attempt_count >= 1),
            reason TEXT NOT NULL, started_at TEXT, updated_at TEXT NOT NULL,
            last_error TEXT, authorized_by TEXT, authorization_reason TEXT,
            checkpoint_fingerprint TEXT, max_attempts INTEGER NOT NULL DEFAULT 3,
            owner_pid INTEGER
        )
    """)
    connection.commit()
    connection.close()

    journal = EventLogRecoveryAttemptStore(database)
    columns = {row["name"] for row in journal._connection.execute("PRAGMA table_info(recovery_attempts)")}
    assert {"owner_run_id", "fencing_token"} <= columns
    attempt = journal.begin_attempt("after-migration", "new schema works")
    assert attempt.owner_run_id
    assert attempt.fencing_token == 1
    journal.finish_success(
        "after-migration", owner_run_id=attempt.owner_run_id,
        fencing_token=attempt.fencing_token,
    )
    journal.close()
