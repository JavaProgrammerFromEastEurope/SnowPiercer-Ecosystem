from contextlib import closing
"""Corrupt counters and ownership metadata must block recovery transitions."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("attempt_count", 0, "invalid attempt_count"),
        ("max_attempts", 0, "inconsistent attempt limits"),
        ("fencing_token", -1, "inconsistent fencing token"),
        ("fencing_token", 2, "inconsistent fencing token"),
    ],
)
def test_corrupt_counters_block_reads_and_transitions(tmp_path, column, value, message):
    database = tmp_path / f"corrupt-{column}-{value}.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("counter-key", "initial attempt")
    store.close()

    # Deliberately bypass schema CHECK constraints to model external corruption.
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            f"UPDATE recovery_attempts SET {column}=? WHERE attempt_key=?",
            (value, attempt.attempt_key),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    with pytest.raises(RecoveryAttemptBlocked, match=message):
        reopened.get(attempt.attempt_key)
    with pytest.raises(RecoveryAttemptBlocked, match=message):
        reopened.begin_attempt(attempt.attempt_key, "must not transition corrupt row")
    assert not reopened._connection.in_transaction
    raw = reopened._connection.execute(
        f"SELECT {column} FROM recovery_attempts WHERE attempt_key=?", (attempt.attempt_key,),
    ).fetchone()
    assert raw[0] == value
    reopened.close()


def test_inconsistent_active_ownership_metadata_blocks_transition(tmp_path):
    database = tmp_path / "corrupt-owner.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("owner-key", "initial attempt")
    store.close()
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "UPDATE recovery_attempts SET lease_expires_at=NULL WHERE attempt_key=?",
            (attempt.attempt_key,),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    with pytest.raises(RecoveryAttemptBlocked, match="inconsistent active ownership metadata"):
        reopened.begin_attempt(attempt.attempt_key, "must not bypass broken ownership")
    assert not reopened._connection.in_transaction
    reopened.close()


def test_interrupted_attempt_clears_pid_and_lease_but_retains_owner_for_audit(tmp_path):
    database = tmp_path / "interrupted-owner.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("interrupted-key", "initial attempt")
    # Model an owner process that no longer exists.
    with store._connection:
        store._connection.execute(
            "UPDATE recovery_attempts SET owner_pid=?, owner_run_id=? "
            "WHERE attempt_key=?",
            (2_000_000_000, "stale-owner-run", attempt.attempt_key),
        )
    # The high PID is expected not to exist in the isolated test environment.
    store._connection.commit()
    with pytest.raises(RecoveryAttemptBlocked, match="interrupted"):
        store.begin_attempt(attempt.attempt_key, "detect interrupted attempt")
    row = store._connection.execute(
        "SELECT status, owner_pid, owner_run_id, lease_expires_at FROM recovery_attempts WHERE attempt_key=?",
        (attempt.attempt_key,),
    ).fetchone()
    assert tuple(row) == (RecoveryAttemptStatus.FAILED.value, None, "stale-owner-run", None)
    assert not store._connection.in_transaction
    store.close()
