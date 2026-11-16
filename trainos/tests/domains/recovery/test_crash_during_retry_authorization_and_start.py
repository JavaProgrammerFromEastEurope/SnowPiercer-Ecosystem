"""Crash-boundary regressions for retry authorization and attempt startup."""
from multiprocessing import get_context
import os

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _CommitThenExit:
    """Exit the worker immediately after a selected durable COMMIT."""
    def __init__(self, connection, exit_code=73):
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


def _crash_after_retry_authorization(database, ready):
    store = EventLogRecoveryAttemptStore(database)
    raw = store._connection
    store._connection = _CommitThenExit(raw, 73)
    ready.set()
    # The first commit after arming is authorize_retry's durable transition.
    store.authorize_retry(
        "crash-retry", operator="operator-122", reason="reviewed after failure",
    )
    os._exit(74)  # pragma: no cover - the armed commit must exit first


def _crash_after_new_attempt_commit(database):
    store = EventLogRecoveryAttemptStore(database)
    raw = store._connection
    store._connection = _CommitThenExit(raw, 75)
    # RETRY_AUTHORIZED -> IN_PROGRESS commits durably, then process dies before
    # begin_attempt() can return the new owner identity to its caller.
    store.begin_attempt("crash-start", "restart authorized recovery", max_attempts=4)
    os._exit(76)  # pragma: no cover - the armed commit must exit first


def test_restart_reconciles_crash_after_retry_authorization_commit(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "crash-after-authorize.sqlite")
    setup = EventLogRecoveryAttemptStore(database)
    first = setup.begin_attempt("crash-retry", "initial attempt", max_attempts=4)
    setup.finish_failure(
        "crash-retry", "controlled failure", owner_run_id=first.owner_run_id,
        fencing_token=first.fencing_token,
    )
    setup.close()

    ready = context.Event()
    worker = context.Process(target=_crash_after_retry_authorization, args=(database, ready))
    worker.start()
    try:
        assert ready.wait(timeout=10)
        worker.join(timeout=15)
        assert not worker.is_alive()
        assert worker.exitcode == 73
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)

    recovered = EventLogRecoveryAttemptStore(database)
    try:
        authorized = recovered.get("crash-retry")
        assert authorized is not None
        assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        assert authorized.authorized_by == "operator-122"
        assert authorized.authorization_reason == "reviewed after failure"
        assert authorized.attempt_count == 1
        assert authorized.fencing_token == first.fencing_token

        started = recovered.begin_attempt("crash-retry", "resume authorized recovery", max_attempts=4)
        assert started.status is RecoveryAttemptStatus.IN_PROGRESS
        assert started.attempt_count == 2
        assert started.fencing_token == first.fencing_token + 1
        assert started.owner_run_id
        with pytest.raises(RecoveryAttemptBlocked, match="already in progress"):
            recovered.begin_attempt("crash-retry", "must not duplicate active attempt", max_attempts=4)
        durable = recovered.get("crash-retry")
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.IN_PROGRESS
        assert durable.attempt_count == 2
        assert durable.fencing_token == started.fencing_token
        assert durable.owner_run_id == started.owner_run_id
    finally:
        recovered.close()


def test_restart_reconciles_crash_after_new_attempt_commit_before_return(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "crash-after-start.sqlite")
    setup = EventLogRecoveryAttemptStore(database)
    first = setup.begin_attempt("crash-start", "initial attempt", max_attempts=4)
    setup.finish_failure(
        "crash-start", "controlled failure", owner_run_id=first.owner_run_id,
        fencing_token=first.fencing_token,
    )
    setup.authorize_retry(
        "crash-start", operator="operator-122", reason="approved restart",
    )
    setup.close()

    worker = context.Process(target=_crash_after_new_attempt_commit, args=(database,))
    worker.start()
    worker.join(timeout=15)
    try:
        assert not worker.is_alive()
        assert worker.exitcode == 75
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)

    recovered = EventLogRecoveryAttemptStore(database)
    try:
        durable = recovered.get("crash-start")
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.IN_PROGRESS
        assert durable.attempt_count == 2
        assert durable.fencing_token == first.fencing_token + 1
        assert durable.owner_run_id
        crashed_owner = durable.owner_run_id

        # The retry is not silently repeated. First call reconciles the dead owner
        # into FAILED and requires explicit authorization, then a new run may begin.
        with pytest.raises(RecoveryAttemptBlocked, match="interrupted"):
            recovered.begin_attempt("crash-start", "reconcile interrupted start", max_attempts=4)
        failed = recovered.get("crash-start")
        assert failed is not None
        assert failed.status is RecoveryAttemptStatus.FAILED
        # Keep the former run UUID as forensic history while clearing its lease.
        assert failed.owner_run_id == crashed_owner
        assert failed.lease_expires_at is None
        assert failed.attempt_count == 2
        assert failed.fencing_token == first.fencing_token + 1

        recovered.authorize_retry(
            "crash-start", operator="operator-122", reason="confirmed interrupted start",
        )
        resumed = recovered.begin_attempt("crash-start", "start after explicit re-authorization", max_attempts=4)
        assert resumed.status is RecoveryAttemptStatus.IN_PROGRESS
        assert resumed.attempt_count == 3
        assert resumed.fencing_token == first.fencing_token + 2
        assert resumed.owner_run_id != crashed_owner
        assert resumed.owner_run_id
    finally:
        recovered.close()
