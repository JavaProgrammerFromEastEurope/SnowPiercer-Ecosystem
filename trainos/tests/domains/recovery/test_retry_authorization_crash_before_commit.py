"""A crash before the retry-authorization COMMIT must not grant permission."""
import os
from multiprocessing import get_context

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _ExitBeforeCommit:
    """Proxy a SQLite connection and die immediately before COMMIT reaches SQLite."""
    def __init__(self, connection, exit_code=78):
        self._connection = connection
        self._exit_code = exit_code

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def commit(self):
        # Deliberately do not delegate: the authorization UPDATE remains uncommitted.
        os._exit(self._exit_code)


def _crash_before_authorization_commit(database):
    store = EventLogRecoveryAttemptStore(database)
    store._connection = _ExitBeforeCommit(store._connection)
    store.authorize_retry(
        "retry-precommit-crash",
        operator="operator-stage141",
        reason="authorization must not survive a pre-commit crash",
    )
    os._exit(79)  # pragma: no cover - commit proxy must terminate first


def test_crash_before_retry_authorization_commit_does_not_grant_retry(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "retry-precommit-crash.sqlite")
    setup = EventLogRecoveryAttemptStore(database)
    try:
        initial = setup.begin_attempt("retry-precommit-crash", "initial attempt", max_attempts=3)
        failed = setup.finish_failure(
            initial.attempt_key,
            "controlled failure",
            owner_run_id=initial.owner_run_id,
            fencing_token=initial.fencing_token,
        )
        assert failed.status is RecoveryAttemptStatus.FAILED
        assert failed.attempt_count == 1
        assert failed.fencing_token == 1
    finally:
        setup.close()

    worker = context.Process(target=_crash_before_authorization_commit, args=(database,))
    worker.start()
    worker.join(timeout=15)
    try:
        assert not worker.is_alive(), "crash simulation process did not exit"
        assert worker.exitcode == 78
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        after_crash = reopened.get("retry-precommit-crash")
        assert after_crash == failed
        assert after_crash is not None
        assert after_crash.status is RecoveryAttemptStatus.FAILED
        assert after_crash.authorized_by is None
        assert after_crash.authorization_reason is None
        assert after_crash.attempt_count == 1
        assert after_crash.fencing_token == 1

        # A failed authorization transaction must not be treated as permission to start.
        with pytest.raises(RecoveryAttemptBlocked, match="authorize retry explicitly"):
            reopened.begin_attempt("retry-precommit-crash", "must remain blocked", max_attempts=3)
        assert reopened.get("retry-precommit-crash") == after_crash

        # A fresh, committed operator decision remains the only path to a new attempt.
        reopened.authorize_retry(
            "retry-precommit-crash",
            operator="operator-stage141-recovery",
            reason="re-authorized after reviewing crash evidence",
        )
        started = reopened.begin_attempt(
            "retry-precommit-crash", "start after fresh authorization", max_attempts=3,
        )
        assert started.status is RecoveryAttemptStatus.IN_PROGRESS
        assert started.attempt_count == 2
        assert started.fencing_token == 2
        assert started.owner_run_id and started.owner_run_id != initial.owner_run_id
    finally:
        reopened.close()
