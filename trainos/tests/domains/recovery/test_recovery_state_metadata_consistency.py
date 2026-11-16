from contextlib import closing
"""Persisted recovery states must not contradict their error metadata."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


@pytest.mark.parametrize(
    "target_status,corrupt_error,expected_fragment",
    [
        (RecoveryAttemptStatus.IN_PROGRESS, "stale error", "inconsistent last_error"),
        (RecoveryAttemptStatus.SUCCEEDED, "old failure", "inconsistent last_error"),
        (RecoveryAttemptStatus.FAILED, None, "inconsistent last_error"),
        (RecoveryAttemptStatus.FAILED, "   ", "inconsistent last_error"),
        (RecoveryAttemptStatus.RETRY_AUTHORIZED, None, "inconsistent last_error"),
        (RecoveryAttemptStatus.RETRY_AUTHORIZED, "  ", "inconsistent last_error"),
    ],
)
def test_state_and_last_error_contradictions_fail_closed_and_preserve_row(
    tmp_path, target_status, corrupt_error, expected_fragment
):
    database = tmp_path / f"state-error-{target_status.value}-{repr(corrupt_error)}.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("state-key", "initial attempt", max_attempts=3)
    if target_status in (RecoveryAttemptStatus.FAILED, RecoveryAttemptStatus.RETRY_AUTHORIZED):
        store.finish_failure(
            attempt.attempt_key, "expected controlled failure",
            owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token,
        )
        if target_status is RecoveryAttemptStatus.RETRY_AUTHORIZED:
            store.authorize_retry(attempt.attempt_key, operator="reviewer", reason="approved retry")
    elif target_status is RecoveryAttemptStatus.SUCCEEDED:
        store.finish_success(
            attempt.attempt_key, owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token,
        )
    store.close()

    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "UPDATE recovery_attempts SET last_error=? WHERE attempt_key=?",
            (corrupt_error, attempt.attempt_key),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match=expected_fragment):
            reopened.get(attempt.attempt_key)
        with pytest.raises(RecoveryAttemptBlocked, match=expected_fragment):
            reopened.begin_attempt(attempt.attempt_key, "must not transition corrupt row")
        assert not reopened._connection.in_transaction
        raw = reopened._connection.execute(
            "SELECT status,last_error,attempt_count,fencing_token FROM recovery_attempts WHERE attempt_key=?",
            (attempt.attempt_key,),
        ).fetchone()
        assert tuple(raw) == (target_status.value, corrupt_error, attempt.attempt_count, attempt.fencing_token)
    finally:
        reopened.close()


def test_valid_state_error_metadata_and_transitions_remain_supported(tmp_path):
    store = EventLogRecoveryAttemptStore(tmp_path / "valid-state-error.sqlite")
    first = store.begin_attempt("valid-key", "first attempt", max_attempts=3)
    assert first.last_error is None
    failed = store.finish_failure(
        first.attempt_key, "controlled failure",
        owner_run_id=first.owner_run_id, fencing_token=first.fencing_token,
    )
    assert failed.status is RecoveryAttemptStatus.FAILED
    assert failed.last_error == "controlled failure"
    authorized = store.authorize_retry(first.attempt_key, operator="reviewer", reason="reviewed")
    assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    assert authorized.last_error == "controlled failure"
    second = store.begin_attempt(first.attempt_key, "approved retry")
    assert second.status is RecoveryAttemptStatus.IN_PROGRESS
    assert second.last_error is None
    succeeded = store.finish_success(
        second.attempt_key, owner_run_id=second.owner_run_id, fencing_token=second.fencing_token,
    )
    assert succeeded.status is RecoveryAttemptStatus.SUCCEEDED
    assert succeeded.last_error is None
    store.close()
