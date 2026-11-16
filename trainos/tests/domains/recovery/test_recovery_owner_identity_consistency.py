from contextlib import closing
"""Inconsistent active owner identity must never be treated as abandoned work."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
)


@pytest.mark.parametrize("owner_pid", [None, 0, "not-a-pid"])
def test_unknown_or_invalid_pid_cannot_authorize_takeover(tmp_path, owner_pid):
    database = tmp_path / "owner-identity.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("owner-identity-key", "active work")
    store.close()
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "UPDATE recovery_attempts SET owner_pid=? WHERE attempt_key=?",
            (owner_pid, attempt.attempt_key),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    # Reads remain available so startup reconciliation can return a precise BLOCKED
    # assessment; attempting to take over must not rewrite the active row as FAILED.
    state = reopened.get(attempt.attempt_key)
    assert state is not None and state.status.value == "in_progress"
    with pytest.raises(RecoveryAttemptBlocked, match="owner PID"):
        reopened.begin_attempt(attempt.attempt_key, "must not take over unknown owner")
    assert not reopened._connection.in_transaction
    raw = reopened._connection.execute(
        "SELECT status, owner_pid, owner_run_id, fencing_token FROM recovery_attempts WHERE attempt_key=?",
        (attempt.attempt_key,),
    ).fetchone()
    assert tuple(raw) == ("in_progress", owner_pid, attempt.owner_run_id, attempt.fencing_token)
    reopened.close()


def test_missing_run_identity_with_modern_fencing_token_is_corrupt(tmp_path):
    database = tmp_path / "missing-run-id.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("missing-run-id-key", "active work")
    with store._connection:
        store._connection.execute(
            "UPDATE recovery_attempts SET owner_run_id=NULL WHERE attempt_key=?",
            (attempt.attempt_key,),
        )
    with pytest.raises(RecoveryAttemptBlocked, match="inconsistent legacy ownership metadata"):
        store.get(attempt.attempt_key)
    assert not store._connection.in_transaction
    store.close()


def test_legacy_pid_only_attempt_remains_readable(tmp_path):
    database = tmp_path / "legacy-owner.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("legacy-owner-key", "active work")
    with store._connection:
        store._connection.execute(
            "UPDATE recovery_attempts SET owner_run_id=NULL, fencing_token=0, lease_expires_at=NULL "
            "WHERE attempt_key=?", (attempt.attempt_key,),
        )
    state = store.get(attempt.attempt_key)
    assert state is not None
    assert state.owner_run_id is None
    assert state.fencing_token == 0
    store.close()
