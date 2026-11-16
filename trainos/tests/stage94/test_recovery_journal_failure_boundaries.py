from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def test_failed_terminal_transition_rolls_back_and_connection_remains_usable(tmp_path):
    database = tmp_path / "attempts.sqlite"
    journal = EventLogRecoveryAttemptStore(database)
    attempt = journal.begin_attempt("finish-failure", "test terminal transition")
    with managed_sqlite_connection(database) as connection:
        connection.execute("""
            CREATE TRIGGER reject_success
            BEFORE UPDATE ON recovery_attempts
            WHEN NEW.status = 'succeeded'
            BEGIN SELECT RAISE(ABORT, 'injected commit-boundary failure'); END
        """)

    with pytest.raises(sqlite3.IntegrityError, match="injected commit-boundary failure"):
        journal.finish_success("finish-failure", owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token)

    state = journal.get("finish-failure")
    assert state.status is RecoveryAttemptStatus.IN_PROGRESS
    assert state.last_error is None

    with managed_sqlite_connection(database) as connection:
        connection.execute("DROP TRIGGER reject_success")
    failed = journal.finish_failure("finish-failure", "operator classified failure", owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token)
    assert failed.status is RecoveryAttemptStatus.FAILED
    assert failed.last_error == "operator classified failure"
    journal.close()


def test_legacy_stage89_journal_migrates_without_losing_attempt_state(tmp_path):
    database = tmp_path / "legacy.sqlite"
    with managed_sqlite_connection(database) as connection:
        connection.execute("""
            CREATE TABLE recovery_attempts (
                attempt_key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL CHECK(attempt_count >= 1),
                reason TEXT NOT NULL,
                started_at TEXT,
                updated_at TEXT NOT NULL,
                last_error TEXT,
                authorized_by TEXT,
                authorization_reason TEXT
            )
        """)
        connection.execute(
            "INSERT INTO recovery_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy", "failed", 1, "old journal", "2026-01-01T00:00:00+00:00",
             "2026-01-01T00:00:01+00:00", "old failure", None, None),
        )

    journal = EventLogRecoveryAttemptStore(database)
    state = journal.get("legacy")
    assert state.status is RecoveryAttemptStatus.FAILED
    assert state.attempt_count == 1
    assert state.reason == "old journal"
    assert state.last_error == "old failure"
    assert state.checkpoint_fingerprint is None
    assert state.max_attempts == 3
    # Migrated state remains usable with the newer retry workflow.
    authorized = journal.authorize_retry("legacy", operator="reviewer", reason="reviewed")
    assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    journal.close()


def test_finish_transition_rejects_non_in_progress_without_damaging_terminal_state(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    attempt = journal.begin_attempt("terminal", "finish once")
    journal.finish_success("terminal", owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token)
    with pytest.raises(RecoveryAttemptBlocked, match="no in-progress"):
        journal.finish_failure("terminal", "late competing result", owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token)
    assert journal.get("terminal").status is RecoveryAttemptStatus.SUCCEEDED
    journal.close()
