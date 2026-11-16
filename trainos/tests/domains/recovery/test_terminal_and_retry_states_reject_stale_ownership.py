from contextlib import closing
"""Non-active journal states must not retain contradictory owner metadata."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


@pytest.mark.parametrize("target_status,field,value", [
    ("failed", "owner_pid", 12345),
    ("failed", "lease_expires_at", "2035-01-01T00:00:00+00:00"),
    ("retry_authorized", "owner_pid", 12345),
    ("retry_authorized", "lease_expires_at", "2035-01-01T00:00:00+00:00"),
    ("succeeded", "owner_pid", 12345),
    ("succeeded", "owner_run_id", "stale-owner-uuid"),
    ("succeeded", "lease_expires_at", "2035-01-01T00:00:00+00:00"),
])
def test_non_active_status_with_stale_owner_metadata_fails_closed(
    tmp_path, target_status, field, value
):
    database = tmp_path / f"stale-owner-{target_status}-{field}.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("stale-owner-key", "initial attempt", max_attempts=3)
    if target_status == "failed":
        store.finish_failure(
            attempt.attempt_key, "controlled failure",
            owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token,
        )
    elif target_status == "retry_authorized":
        store.finish_failure(
            attempt.attempt_key, "controlled failure",
            owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token,
        )
        store.authorize_retry(attempt.attempt_key, operator="reviewer", reason="approved")
    else:
        store.finish_success(
            attempt.attempt_key,
            owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token,
        )
    store.close()

    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            f"UPDATE recovery_attempts SET {field}=? WHERE attempt_key=?",
            (value, attempt.attempt_key),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match="ownership metadata outside an active attempt"):
            reopened.get(attempt.attempt_key)
        with pytest.raises(RecoveryAttemptBlocked, match="ownership metadata outside an active attempt"):
            reopened.begin_attempt(attempt.attempt_key, "must not overwrite stale owner")
        assert not reopened._connection.in_transaction
        raw = reopened._connection.execute(
            "SELECT status, owner_pid, owner_run_id, lease_expires_at FROM recovery_attempts WHERE attempt_key=?",
            (attempt.attempt_key,),
        ).fetchone()
        assert raw[0] == target_status
        assert raw[{"owner_pid": 1, "owner_run_id": 2, "lease_expires_at": 3}[field]] == value
    finally:
        reopened.close()
