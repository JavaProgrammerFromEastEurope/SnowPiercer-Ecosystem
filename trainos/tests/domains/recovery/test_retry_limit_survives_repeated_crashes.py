"""Repeated process crashes must not bypass the durable recovery-attempt limit."""
from multiprocessing import get_context
import os

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _CommitThenExit:
    """Exit immediately after the next durable commit, without Python cleanup."""
    def __init__(self, connection, exit_code=83):
        self._connection = connection
        self._exit_code = exit_code
        self._armed = True

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def commit(self):
        self._connection.commit()
        if self._armed:
            self._armed = False
            os._exit(self._exit_code)


def _crash_after_attempt_start(database):
    store = EventLogRecoveryAttemptStore(database)
    store._connection = _CommitThenExit(store._connection)
    store.begin_attempt("bounded-crashes", "start attempt that will crash", max_attempts=2)
    os._exit(84)  # pragma: no cover - commit wrapper must exit first


def _reconcile_interrupted(store, key):
    with pytest.raises(RecoveryAttemptBlocked, match="interrupted"):
        store.begin_attempt(key, "reconcile dead owner", max_attempts=2)
    row = store.get(key)
    assert row is not None
    assert row.status is RecoveryAttemptStatus.FAILED
    assert row.lease_expires_at is None
    return row


def test_repeated_crash_cannot_exceed_max_attempts_after_restart(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "bounded-crashes.sqlite")
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt("bounded-crashes", "initial attempt", max_attempts=2)
    store.finish_failure(
        "bounded-crashes", "first attempt failed", owner_run_id=first.owner_run_id,
        fencing_token=first.fencing_token,
    )
    store.authorize_retry(
        "bounded-crashes", operator="operator-123", reason="approved second attempt",
    )
    store.close()

    worker = context.Process(target=_crash_after_attempt_start, args=(database,))
    worker.start()
    worker.join(timeout=15)
    try:
        assert not worker.is_alive()
        assert worker.exitcode == 83
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        crashed = restarted.get("bounded-crashes")
        assert crashed is not None
        assert crashed.status is RecoveryAttemptStatus.IN_PROGRESS
        assert crashed.attempt_count == 2
        assert crashed.max_attempts == 2
        assert crashed.fencing_token == first.fencing_token + 1
        crashed_owner = crashed.owner_run_id
        assert crashed_owner

        failed = _reconcile_interrupted(restarted, "bounded-crashes")
        assert failed.attempt_count == 2
        assert failed.fencing_token == first.fencing_token + 1
        # Preserve the prior run UUID as forensic metadata, but clear active ownership.
        assert failed.owner_run_id == crashed_owner
        assert failed.owner_pid is None
        assert failed.lease_expires_at is None

        # Explicit retry authorization is not enough to bypass the durable limit.
        with pytest.raises(RecoveryAttemptBlocked, match="maximum recovery attempts reached"):
            restarted.authorize_retry(
                "bounded-crashes", operator="operator-123", reason="attempt limit reached",
            )
        with pytest.raises(RecoveryAttemptBlocked, match="maximum recovery attempts reached"):
            restarted.begin_attempt("bounded-crashes", "attempt-limit bypass", max_attempts=99)

        final = restarted.get("bounded-crashes")
        assert final is not None
        assert final.status is RecoveryAttemptStatus.FAILED
        assert final.attempt_count == 2
        assert final.max_attempts == 2
        assert final.fencing_token == first.fencing_token + 1
        assert final.owner_pid is None
        assert final.lease_expires_at is None
    finally:
        restarted.close()


def test_max_attempts_cannot_be_raised_by_later_begin_call(tmp_path):
    database = tmp_path / "max-attempts-immutable.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    try:
        first = store.begin_attempt("fixed-limit", "first attempt", max_attempts=1)
        store.finish_failure(
            "fixed-limit", "failure at configured limit", owner_run_id=first.owner_run_id,
            fencing_token=first.fencing_token,
        )
        with pytest.raises(RecoveryAttemptBlocked, match="maximum recovery attempts reached"):
            store.authorize_retry(
                "fixed-limit", operator="operator-123", reason="attempt limit reached",
            )
        with pytest.raises(RecoveryAttemptBlocked, match="maximum recovery attempts reached"):
            store.begin_attempt("fixed-limit", "try to raise limit", max_attempts=10)
        final = store.get("fixed-limit")
        assert final is not None
        assert final.status is RecoveryAttemptStatus.FAILED
        assert final.attempt_count == 1
        assert final.max_attempts == 1
    finally:
        store.close()
