from contextlib import closing
"""A retry authorization must be complete and bound before it can be consumed."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


@pytest.mark.parametrize(
    "field,value,error_fragment",
    [
        ("authorized_by", None, "authorization operator"),
        ("authorized_by", "   ", "authorization operator"),
        ("authorization_reason", None, "authorization reason"),
        ("authorization_reason", "  ", "authorization reason"),
        ("checkpoint_fingerprint", "", "checkpoint fingerprint"),
        ("checkpoint_fingerprint", "   ", "checkpoint fingerprint"),
    ],
)
def test_corrupt_retry_authorization_fails_closed_and_preserves_row(
    tmp_path, field, value, error_fragment
):
    database = tmp_path / f"corrupt-auth-{field}-{repr(value)}.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt(
        "retry-auth-key", "first attempt", checkpoint_fingerprint="checkpoint-v1", max_attempts=3,
    )
    store.finish_failure(
        first.attempt_key, "controlled failure",
        owner_run_id=first.owner_run_id, fencing_token=first.fencing_token,
    )
    store.authorize_retry(
        first.attempt_key, operator="reviewer", reason="reviewed failure",
        checkpoint_fingerprint="checkpoint-v1",
    )
    store.close()

    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            f"UPDATE recovery_attempts SET {field}=? WHERE attempt_key=?",
            (value, first.attempt_key),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match=error_fragment):
            reopened.get(first.attempt_key)
        with pytest.raises(RecoveryAttemptBlocked, match=error_fragment):
            reopened.begin_attempt(
                first.attempt_key, "must not consume corrupt authorization",
                checkpoint_fingerprint="checkpoint-v1",
            )
        assert not reopened._connection.in_transaction
        raw = reopened._connection.execute(
            f"SELECT status, {field}, attempt_count, fencing_token FROM recovery_attempts WHERE attempt_key=?",
            (first.attempt_key,),
        ).fetchone()
        assert raw[0] == RecoveryAttemptStatus.RETRY_AUTHORIZED.value
        assert raw[1] == value
        assert raw[2:] == (1, 1)
    finally:
        reopened.close()


def test_checkpoint_mismatch_does_not_consume_valid_retry_authorization(tmp_path):
    store = EventLogRecoveryAttemptStore(tmp_path / "checkpoint-mismatch.sqlite")
    first = store.begin_attempt(
        "checkpoint-bound", "first attempt", checkpoint_fingerprint="checkpoint-v1", max_attempts=3,
    )
    store.finish_failure(
        first.attempt_key, "controlled failure",
        owner_run_id=first.owner_run_id, fencing_token=first.fencing_token,
    )
    store.authorize_retry(
        first.attempt_key, operator="reviewer", reason="reviewed checkpoint",
        checkpoint_fingerprint="checkpoint-approved",
    )

    with pytest.raises(RecoveryAttemptBlocked, match="checkpoint changed after retry authorization"):
        store.begin_attempt(first.attempt_key, "wrong checkpoint", checkpoint_fingerprint="checkpoint-other")

    unchanged = store.get(first.attempt_key)
    assert unchanged is not None
    assert unchanged.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    assert unchanged.attempt_count == 1 and unchanged.fencing_token == 1
    assert unchanged.authorized_by == "reviewer"
    assert unchanged.authorization_reason == "reviewed checkpoint"
    assert unchanged.checkpoint_fingerprint == "checkpoint-approved"

    started = store.begin_attempt(first.attempt_key, "approved checkpoint", checkpoint_fingerprint="checkpoint-approved")
    assert started.status is RecoveryAttemptStatus.IN_PROGRESS
    assert started.attempt_count == 2 and started.fencing_token == 2
    assert started.authorized_by is None and started.authorization_reason is None
    store.close()
