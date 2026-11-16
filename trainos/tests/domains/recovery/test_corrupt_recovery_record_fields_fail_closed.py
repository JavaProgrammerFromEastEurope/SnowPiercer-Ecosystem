from contextlib import closing
"""Externally corrupted identity, reason, timestamps and limits must fail closed."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
)


@pytest.mark.parametrize(
    "column,value,fragment,lookup_key",
    [
        ("reason", "   ", "invalid reason", "corrupt-field-key"),
        ("reason", sqlite3.Binary(b"17"), "invalid reason", "corrupt-field-key"),
        ("started_at", None, "missing started_at", "corrupt-field-key"),
        ("started_at", "not-a-time", "invalid started_at", "corrupt-field-key"),
        ("updated_at", "2026-99-99T00:00:00+00:00", "invalid updated_at", "corrupt-field-key"),
        ("updated_at", "2026-01-01T00:00:00", "timezone-naive updated_at", "corrupt-field-key"),
        ("max_attempts", 0, "attempt limits", "corrupt-field-key"),
        ("max_attempts", "three", "attempt limits", "corrupt-field-key"),
    ],
)
def test_corrupt_record_fields_block_reads_and_transitions_without_repair(
    tmp_path, column, value, fragment, lookup_key
):
    database = tmp_path / f"corrupt-{column}-{repr(value)}.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt(lookup_key, "valid original reason", max_attempts=3)
    store.close()

    with closing(sqlite3.connect(database)) as connection, connection:
        # Deliberately bypass CHECK constraints to model a damaged/external writer.
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(f"UPDATE recovery_attempts SET {column}=? WHERE attempt_key=?", (value, lookup_key))

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match=fragment):
            reopened.get(lookup_key)
        with pytest.raises(RecoveryAttemptBlocked, match=fragment):
            reopened.begin_attempt(lookup_key, "must not proceed")
        assert not reopened._connection.in_transaction
        raw = reopened._connection.execute(
            f"SELECT {column} FROM recovery_attempts WHERE attempt_key=?", (lookup_key,)
        ).fetchone()
        assert raw[0] == value
        count = reopened._connection.execute(
            "SELECT attempt_count FROM recovery_attempts WHERE attempt_key=?", (lookup_key,)
        ).fetchone()[0]
        assert count == attempt.attempt_count
    finally:
        reopened.close()


def test_blank_persisted_key_blocks_absent_key_lookup_and_new_attempt(tmp_path):
    database = tmp_path / "corrupt-key.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    store.begin_attempt("valid-key", "valid reason")
    store.close()
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute("UPDATE recovery_attempts SET attempt_key='   '")

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match="invalid attempt_key"):
            reopened.get("valid-key")
        with pytest.raises(RecoveryAttemptBlocked, match="invalid attempt_key"):
            reopened.begin_attempt("valid-key", "must not create around corrupt row")
        assert reopened._connection.execute("SELECT COUNT(*) FROM recovery_attempts").fetchone()[0] == 1
        assert reopened._connection.execute("SELECT attempt_key FROM recovery_attempts").fetchone()[0] == "   "
    finally:
        reopened.close()


def test_valid_record_fields_still_support_normal_lifecycle(tmp_path):
    store = EventLogRecoveryAttemptStore(tmp_path / "valid-fields.sqlite")
    attempt = store.begin_attempt("valid-key", "valid reason", max_attempts=2)
    assert attempt.reason == "valid reason"
    assert attempt.max_attempts == 2
    failed = store.finish_failure(
        attempt.attempt_key, "controlled failure",
        owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token,
    )
    assert failed.last_error == "controlled failure"
    store.close()
