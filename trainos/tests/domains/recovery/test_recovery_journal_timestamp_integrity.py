from contextlib import closing
"""Malformed recovery timestamps must fail closed as journal corruption."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("updated_at", "not-a-timestamp", "invalid updated_at timestamp"),
        ("updated_at", "2026-10-22T12:00:00", "timezone-naive updated_at timestamp"),
        ("started_at", "2026-10-22T12:00:00", "timezone-naive started_at timestamp"),
        ("lease_expires_at", "not-a-timestamp", "invalid lease_expires_at timestamp"),
        ("lease_expires_at", "2026-10-22T12:00:00", "timezone-naive lease_expires_at timestamp"),
    ],
)
def test_malformed_or_naive_timestamp_blocks_reads_and_transitions(
    tmp_path, column, value, message
):
    database = tmp_path / f"timestamp-{column}.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("timestamp-key", "initial attempt")
    store.close()

    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            f"UPDATE recovery_attempts SET {column}=? WHERE attempt_key=?",
            (value, attempt.attempt_key),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    with pytest.raises(RecoveryAttemptBlocked, match=message):
        reopened.get(attempt.attempt_key)
    with pytest.raises(RecoveryAttemptBlocked, match=message):
        reopened.renew_lease(
            attempt.attempt_key,
            owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token,
        )
    assert not reopened._connection.in_transaction
    # The guard does not silently repair or overwrite evidence of corruption.
    raw = reopened._connection.execute(
        f"SELECT {column} FROM recovery_attempts WHERE attempt_key=?",
        (attempt.attempt_key,),
    ).fetchone()
    assert raw[0] == value
    reopened.close()


def test_expired_lease_is_valid_timestamp_but_cannot_be_renewed(tmp_path):
    database = tmp_path / "expired-lease.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("expired-key", "initial attempt")
    expired = "2000-01-01T00:00:00+00:00"
    with store._connection:
        store._connection.execute(
            "UPDATE recovery_attempts SET lease_expires_at=? WHERE attempt_key=?",
            (expired, attempt.attempt_key),
        )
    with pytest.raises(RecoveryAttemptBlocked, match="lease expired"):
        store.renew_lease(
            attempt.attempt_key,
            owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token,
        )
    assert store.get(attempt.attempt_key).lease_expires_at == expired
    assert not store._connection.in_transaction
    store.close()
