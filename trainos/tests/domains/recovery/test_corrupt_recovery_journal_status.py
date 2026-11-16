from contextlib import closing
"""Unknown or inconsistent persisted recovery states must fail closed."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def test_unknown_persisted_status_blocks_reads_and_new_attempts(tmp_path):
    database = tmp_path / "unknown-status.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("corrupt-status", "initial attempt")
    store.close()

    # Model corruption or a newer/foreign writer persisting an unsupported state.
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "UPDATE recovery_attempts SET status=? WHERE attempt_key=?",
            ("recovering_maybe", attempt.attempt_key),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    with pytest.raises(RecoveryAttemptBlocked, match="unknown status.*manual reconciliation"):
        reopened.get(attempt.attempt_key)

    with pytest.raises(RecoveryAttemptBlocked, match="unknown status.*manual reconciliation"):
        reopened.begin_attempt(attempt.attempt_key, "must not overwrite corrupt state")

    assert not reopened._connection.in_transaction
    raw = reopened._connection.execute(
        "SELECT status, attempt_count, fencing_token FROM recovery_attempts WHERE attempt_key=?",
        (attempt.attempt_key,),
    ).fetchone()
    assert tuple(raw) == ("recovering_maybe", 1, 1)
    reopened.close()


def test_known_terminal_status_cannot_be_restarted_under_same_key(tmp_path):
    database = tmp_path / "terminal-status.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("terminal-status", "initial attempt")
    store.finish_success(
        attempt.attempt_key,
        owner_run_id=attempt.owner_run_id,
        fencing_token=attempt.fencing_token,
    )

    with pytest.raises(RecoveryAttemptBlocked, match="already succeeded"):
        store.begin_attempt(attempt.attempt_key, "must use a new key")

    row = store._connection.execute(
        "SELECT status, attempt_count, fencing_token FROM recovery_attempts WHERE attempt_key=?",
        (attempt.attempt_key,),
    ).fetchone()
    assert tuple(row) == (RecoveryAttemptStatus.SUCCEEDED.value, 1, 1)
    assert not store._connection.in_transaction
    store.close()
