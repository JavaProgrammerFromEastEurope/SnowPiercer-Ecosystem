"""A concurrent SQLite writer cannot race journal validation into a mutation."""
import sqlite3
import threading

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def test_writer_commits_corruption_while_new_attempt_waits_for_write_lock(tmp_path):
    database = tmp_path / "concurrent-corruption.sqlite"
    setup = EventLogRecoveryAttemptStore(database)
    active = setup.begin_attempt("healthy-active", "valid active reason")
    sibling = setup.begin_attempt("sibling", "valid sibling reason")
    setup.close()

    writer_has_lock = threading.Event()
    allow_writer_commit = threading.Event()
    writer_errors = []

    def corrupt_sibling_while_holding_write_lock():
        try:
            connection = sqlite3.connect(database, timeout=5.0)
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE recovery_attempts SET reason='   ' WHERE attempt_key=?",
                    ("sibling",),
                )
                writer_has_lock.set()
                if not allow_writer_commit.wait(timeout=5.0):
                    raise AssertionError("test did not release the concurrent writer")
                connection.commit()
            finally:
                connection.close()
        except BaseException as exc:
            writer_errors.append(exc)
            writer_has_lock.set()

    writer = threading.Thread(target=corrupt_sibling_while_holding_write_lock)
    writer.start()
    assert writer_has_lock.wait(timeout=5.0)
    assert not writer_errors

    contender = EventLogRecoveryAttemptStore(database)
    result = []
    contender_started = threading.Event()

    def attempt_transition():
        contender_started.set()
        try:
            contender.begin_attempt("new-attempt", "must fail closed")
        except BaseException as exc:
            result.append(exc)
        else:
            result.append(None)

    thread = threading.Thread(target=attempt_transition)
    thread.start()
    assert contender_started.wait(timeout=5.0)
    # The contender's BEGIN IMMEDIATE cannot pass the writer's lock until the
    # corrupt row is committed; validation must then observe the committed row.
    allow_writer_commit.set()
    writer.join(timeout=5.0)
    thread.join(timeout=5.0)
    try:
        assert not writer.is_alive()
        assert not thread.is_alive()
        assert not writer_errors
        assert len(result) == 1
        assert isinstance(result[0], RecoveryAttemptBlocked)
        assert "invalid reason" in str(result[0])
        assert contender._connection.execute(
            "SELECT COUNT(*) FROM recovery_attempts WHERE attempt_key='new-attempt'"
        ).fetchone()[0] == 0
        healthy = contender.get("healthy-active")
        assert healthy is not None
        assert healthy.status is RecoveryAttemptStatus.IN_PROGRESS
        assert healthy.owner_run_id == active.owner_run_id
        assert healthy.fencing_token == active.fencing_token
        raw_sibling = contender._connection.execute(
            "SELECT reason,attempt_count FROM recovery_attempts WHERE attempt_key='sibling'"
        ).fetchone()
        assert raw_sibling["reason"] == "   "
        assert raw_sibling["attempt_count"] == sibling.attempt_count
        assert not contender._connection.in_transaction
    finally:
        contender.close()
