"""Abrupt process death must leave recovery journal transitions atomic."""
import os
import sqlite3
from multiprocessing import get_context

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _commit_attempt_then_crash(database, attempt_key):
    """Exit without Python cleanup after begin_attempt has committed."""
    store = EventLogRecoveryAttemptStore(database)
    store.begin_attempt(attempt_key, "attempt committed before simulated process crash")
    os._exit(0)


def _crash_during_uncommitted_transition(database, attempt_key):
    """Leave a deliberately partial SQL update uncommitted, then die abruptly."""
    connection = sqlite3.connect(database, timeout=5.0)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        "UPDATE recovery_attempts SET status=?, last_error=?, owner_pid=NULL, "
        "owner_run_id=NULL, lease_expires_at=NULL WHERE attempt_key=?",
        (RecoveryAttemptStatus.FAILED.value, "partial uncommitted write", attempt_key),
    )
    # No COMMIT or connection close: emulate abrupt termination inside a write txn.
    os._exit(17)


def _run_crashing_process(target, args):
    context = get_context("spawn")
    worker = context.Process(target=target, args=args)
    worker.start()
    worker.join(timeout=20)
    if worker.is_alive():
        worker.terminate()
        worker.join(timeout=5)
        raise AssertionError("crash simulation process did not exit")
    return worker.exitcode


def test_committed_attempt_survives_crash_and_uncommitted_transition_rolls_back(tmp_path):
    database = str(tmp_path / "crash-atomicity.sqlite")
    key = "crash-atomicity"

    # The first worker durably creates the row, then exits without closing its store.
    assert _run_crashing_process(_commit_attempt_then_crash, (database, key)) == 0

    observer = EventLogRecoveryAttemptStore(database)
    try:
        committed = observer.get(key)
        assert committed is not None
        assert committed.status is RecoveryAttemptStatus.IN_PROGRESS
        assert committed.attempt_count == 1
        assert committed.fencing_token == 1
        assert committed.owner_run_id
        crashed_owner_pid = committed.owner_pid
        assert crashed_owner_pid is not None and crashed_owner_pid > 0
    finally:
        observer.close()

    # A second process starts to reconcile the row but dies before COMMIT. SQLite
    # must discard the partial update and retain the complete previously committed row.
    assert _run_crashing_process(_crash_during_uncommitted_transition, (database, key)) == 17

    observer = EventLogRecoveryAttemptStore(database)
    try:
        after_crash = observer.get(key)
        assert after_crash == committed
        assert after_crash.status is RecoveryAttemptStatus.IN_PROGRESS
        assert after_crash.owner_pid == crashed_owner_pid
        assert after_crash.owner_run_id == committed.owner_run_id
        assert after_crash.fencing_token == committed.fencing_token
        assert after_crash.last_error is None

        # Once the crashed owner is confirmed dead, normal store logic durably marks
        # the interrupted attempt FAILED instead of accepting a partial row.
        try:
            observer.begin_attempt(key, "reconcile after uncommitted transaction crash")
        except RecoveryAttemptBlocked as exc:
            assert "previous recovery attempt was interrupted" in str(exc)
        else:
            raise AssertionError("interrupted attempt unexpectedly restarted without authorization")

        reconciled = observer.get(key)
        assert reconciled is not None
        assert reconciled.status is RecoveryAttemptStatus.FAILED
        assert reconciled.attempt_count == 1
        assert reconciled.fencing_token == committed.fencing_token
        assert reconciled.owner_pid is None
        assert reconciled.owner_run_id == committed.owner_run_id
        assert reconciled.lease_expires_at is None
        assert reconciled.last_error == (
            "previous attempt was interrupted; explicit retry authorization required"
        )
    finally:
        observer.close()
