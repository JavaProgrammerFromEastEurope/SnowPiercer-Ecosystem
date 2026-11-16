from contextlib import closing
"""Corrupt modern owner metadata must not trigger automatic takeover."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
)


@pytest.mark.parametrize("owner_pid", [-1, -999, 0, None, "not-a-pid", 3.5])
def test_corrupt_modern_owner_pid_blocks_read_and_preserves_durable_row(tmp_path, owner_pid):
    database = tmp_path / "corrupt-modern-owner.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("modern-owner-key", "active recovery")
    store.close()

    # External corruption may bypass application-level validation and SQLite typing.
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "UPDATE recovery_attempts SET owner_pid=? WHERE attempt_key=?",
            (owner_pid, attempt.attempt_key),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    # Inspection remains available, but a transition must fail closed.
    state = reopened.get(attempt.attempt_key)
    assert state is not None and state.status.value == "in_progress"
    with pytest.raises(RecoveryAttemptBlocked, match="owner PID"):
        reopened.begin_attempt(attempt.attempt_key, "must not take over corrupt owner")
    assert not reopened._connection.in_transaction

    raw = reopened._connection.execute(
        "SELECT status, owner_pid, owner_run_id, fencing_token, lease_expires_at "
        "FROM recovery_attempts WHERE attempt_key=?",
        (attempt.attempt_key,),
    ).fetchone()
    assert raw[0] == "in_progress"
    assert raw[1] == owner_pid
    assert raw[2] == attempt.owner_run_id
    assert raw[3] == attempt.fencing_token
    assert raw[4] is not None
    reopened.close()
