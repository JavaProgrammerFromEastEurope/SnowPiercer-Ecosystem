from tests.sqlite_resource_helpers import managed_sqlite_connection
"""A corrupt unrelated journal row must block every state-changing transition."""
import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def test_corrupt_sibling_row_blocks_new_attempt_and_preserves_all_rows(tmp_path):
    database = tmp_path / "sibling-corruption.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt("healthy-active", "valid active reason")
    second = store.begin_attempt("corrupt-sibling", "valid sibling reason")
    store.close()

    with managed_sqlite_connection(database) as connection:
        connection.execute(
            "UPDATE recovery_attempts SET reason='   ' WHERE attempt_key=?",
            ("corrupt-sibling",),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match="invalid reason"):
            reopened.begin_attempt("brand-new", "must not be created")
        assert reopened._connection.execute(
            "SELECT COUNT(*) FROM recovery_attempts WHERE attempt_key='brand-new'"
        ).fetchone()[0] == 0
        rows = reopened._connection.execute(
            "SELECT attempt_key,status,attempt_count,reason,owner_run_id,fencing_token "
            "FROM recovery_attempts ORDER BY attempt_key"
        ).fetchall()
        by_key = {row[0]: row for row in rows}
        assert len(rows) == 2
        assert by_key["healthy-active"][1] == RecoveryAttemptStatus.IN_PROGRESS.value
        assert by_key["healthy-active"][2] == first.attempt_count
        assert by_key["healthy-active"][4] == first.owner_run_id
        assert by_key["healthy-active"][5] == first.fencing_token
        assert by_key["corrupt-sibling"][3] == "   "
        assert by_key["corrupt-sibling"][2] == second.attempt_count
        assert not reopened._connection.in_transaction
    finally:
        reopened.close()


def test_corrupt_sibling_row_blocks_finishing_healthy_attempt(tmp_path):
    database = tmp_path / "sibling-corruption-finish.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    active = store.begin_attempt("healthy-active", "valid active reason")
    store.begin_attempt("corrupt-sibling", "valid sibling reason")
    store.close()

    with managed_sqlite_connection(database) as connection:
        connection.execute(
            "UPDATE recovery_attempts SET updated_at='not-a-timestamp' WHERE attempt_key=?",
            ("corrupt-sibling",),
        )

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match="invalid updated_at"):
            reopened.finish_success(
                active.attempt_key,
                owner_run_id=active.owner_run_id,
                fencing_token=active.fencing_token,
            )
        row = reopened._connection.execute(
            "SELECT status,attempt_count,owner_run_id,fencing_token FROM recovery_attempts WHERE attempt_key=?",
            (active.attempt_key,),
        ).fetchone()
        assert row[0] == RecoveryAttemptStatus.IN_PROGRESS.value
        assert row[1] == active.attempt_count
        assert row[2] == active.owner_run_id
        assert row[3] == active.fencing_token
        assert not reopened._connection.in_transaction
    finally:
        reopened.close()
