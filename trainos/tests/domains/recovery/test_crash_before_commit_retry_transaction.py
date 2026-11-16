"""SQLite must roll back interrupted retry transactions before COMMIT."""
from multiprocessing import get_context
import os

from kernel.command.events import EventLogRecoveryAttemptStore, RecoveryAttemptStatus


class _ExecuteThenExit:
    """Exit after a selected write has executed, before its transaction commits."""
    def __init__(self, connection, sql_prefix, exit_code):
        self._connection = connection
        self._sql_prefix = sql_prefix
        self._exit_code = exit_code
        self._armed = True

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def execute(self, sql, parameters=()):
        result = self._connection.execute(sql, parameters)
        normalized = " ".join(sql.split())
        if self._armed and normalized.startswith(self._sql_prefix):
            self._armed = False
            os._exit(self._exit_code)
        return result


def _crash_during_authorize_retry(database):
    store = EventLogRecoveryAttemptStore(database)
    store._connection = _ExecuteThenExit(
        store._connection,
        "UPDATE recovery_attempts SET status=?, updated_at=?, authorized_by=?,",
        85,
    )
    store.authorize_retry(
        "precommit-authorize", operator="operator-1", reason="approved retry",
    )
    os._exit(86)  # pragma: no cover - armed wrapper must exit first


def _crash_during_first_begin(database):
    store = EventLogRecoveryAttemptStore(database)
    store._connection = _ExecuteThenExit(
        store._connection,
        "INSERT INTO recovery_attempts",
        87,
    )
    store.begin_attempt("precommit-insert", "initial attempt", max_attempts=2)
    os._exit(88)  # pragma: no cover - armed wrapper must exit first


def _run_crash_process(target, database, expected_exit):
    process = get_context("spawn").Process(target=target, args=(str(database),))
    process.start()
    process.join(timeout=15)
    try:
        assert not process.is_alive(), "crash-injection child did not exit"
        assert process.exitcode == expected_exit
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)


def test_crash_after_retry_update_before_commit_rolls_back_and_retry_is_recoverable(tmp_path):
    database = tmp_path / "precommit-authorize.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt("precommit-authorize", "first attempt", max_attempts=2)
    store.finish_failure(
        "precommit-authorize", "first attempt failed", owner_run_id=first.owner_run_id,
        fencing_token=first.fencing_token,
    )
    before = store.get("precommit-authorize")
    assert before is not None and before.status is RecoveryAttemptStatus.FAILED
    store.close()

    _run_crash_process(_crash_during_authorize_retry, database, 85)

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        rolled_back = restarted.get("precommit-authorize")
        assert rolled_back is not None
        assert rolled_back.status is RecoveryAttemptStatus.FAILED
        assert rolled_back.attempt_count == before.attempt_count == 1
        assert rolled_back.max_attempts == before.max_attempts == 2
        assert rolled_back.fencing_token == before.fencing_token
        assert rolled_back.authorized_by is None
        assert rolled_back.authorization_reason is None
        assert rolled_back.owner_run_id is None
        assert rolled_back.lease_expires_at is None

        authorized = restarted.authorize_retry(
            "precommit-authorize", operator="operator-2", reason="retry after recovered rollback",
        )
        assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        assert authorized.authorized_by == "operator-2"
        assert authorized.attempt_count == 1

        started = restarted.begin_attempt("precommit-authorize", "second attempt")
        assert started.status is RecoveryAttemptStatus.IN_PROGRESS
        assert started.attempt_count == 2
        assert started.fencing_token == before.fencing_token + 1
        assert started.owner_run_id
    finally:
        restarted.close()


def test_crash_after_first_attempt_insert_before_commit_leaves_no_partial_row(tmp_path):
    database = tmp_path / "precommit-insert.sqlite"
    _run_crash_process(_crash_during_first_begin, database, 87)

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        assert restarted.get("precommit-insert") is None
        started = restarted.begin_attempt(
            "precommit-insert", "first attempt after rollback", max_attempts=2,
        )
        assert started.status is RecoveryAttemptStatus.IN_PROGRESS
        assert started.attempt_count == 1
        assert started.max_attempts == 2
        assert started.fencing_token == 1
        assert started.owner_run_id
    finally:
        restarted.close()
