from contextlib import closing
"""Concurrent interruption reconciliation and retry authorization stay serialized."""
from multiprocessing import get_context
import sqlite3

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _reconcile_interrupted(database, barrier, result_queue):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            result = store.begin_attempt(
                "interrupted-race", "reconcile interrupted attempt", max_attempts=2,
            )
        except RecoveryAttemptBlocked as exc:
            result_queue.put(("reconcile", "blocked", str(exc)))
        else:
            result_queue.put(("reconcile", "started", result.status.value))
    except BaseException as exc:
        result_queue.put(("reconcile", "error", repr(exc)))
        raise
    finally:
        store.close()


def _authorize_interrupted_retry(database, barrier, result_queue):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            result = store.authorize_retry(
                "interrupted-race", operator="race-operator", reason="reviewed after crash",
            )
        except RecoveryAttemptBlocked as exc:
            result_queue.put(("authorize", "blocked", str(exc)))
        else:
            result_queue.put(("authorize", "authorized", result.status.value))
    except BaseException as exc:
        result_queue.put(("authorize", "error", repr(exc)))
        raise
    finally:
        store.close()


def test_interrupted_attempt_reconciliation_races_retry_authorization(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "interrupted-race.sqlite")
    store = EventLogRecoveryAttemptStore(database)
    try:
        initial = store.begin_attempt("interrupted-race", "attempt before simulated crash", max_attempts=2)
        assert initial.status is RecoveryAttemptStatus.IN_PROGRESS
        store.close()

        # Simulate a process that has exited: the owner PID is guaranteed not to
        # exist on supported OSes, so begin_attempt must reconcile IN_PROGRESS -> FAILED.
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute(
                "UPDATE recovery_attempts SET owner_pid=?, lease_expires_at=? WHERE attempt_key=?",
                (2_000_000_000, "2000-01-01T00:00:00+00:00", "interrupted-race"),
            )
    except BaseException:
        try:
            store.close()
        except Exception:
            pass
        raise

    barrier = context.Barrier(2)
    result_queue = context.Queue()
    workers = [
        context.Process(target=_reconcile_interrupted, args=(database, barrier, result_queue)),
        context.Process(target=_authorize_interrupted_retry, args=(database, barrier, result_queue)),
    ]
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join(timeout=20)
        assert all(not worker.is_alive() for worker in workers)
        assert [worker.exitcode for worker in workers] == [0, 0]
        results = [result_queue.get(timeout=5) for _ in workers]
        by_name = {result[0]: result for result in results}
        assert set(by_name) == {"reconcile", "authorize"}, results
        assert by_name["reconcile"][1] == "blocked", results
        assert "previous recovery attempt was interrupted" in by_name["reconcile"][2], results
        assert by_name["authorize"][1] in {"blocked", "authorized"}, results
        if by_name["authorize"][1] == "blocked":
            assert "retry can only be authorized for a failed attempt" in by_name["authorize"][2], results
        else:
            assert by_name["authorize"][2] == RecoveryAttemptStatus.RETRY_AUTHORIZED.value, results
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        result_queue.close()
        result_queue.join_thread()

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        current = restarted.get("interrupted-race")
        assert current is not None
        assert current.status in {RecoveryAttemptStatus.FAILED, RecoveryAttemptStatus.RETRY_AUTHORIZED}
        assert current.attempt_count == 1
        assert current.max_attempts == 2
        assert current.fencing_token == initial.fencing_token
        assert current.owner_pid is None
        assert current.owner_run_id == initial.owner_run_id  # retained for forensic traceability
        assert current.lease_expires_at is None
        if current.status is RecoveryAttemptStatus.FAILED:
            assert current.authorized_by is None
            assert current.authorization_reason is None
            authorized = restarted.authorize_retry(
                "interrupted-race", operator="follow-up-operator", reason="authorize after reconciliation",
            )
            assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        else:
            assert current.authorized_by == "race-operator"
            assert current.authorization_reason == "reviewed after crash"

        # Exactly one explicitly authorized retry can consume attempt 2 and fence 2.
        second = restarted.begin_attempt("interrupted-race", "single authorized retry")
        assert second.status is RecoveryAttemptStatus.IN_PROGRESS
        assert second.attempt_count == 2
        assert second.max_attempts == 2
        assert second.fencing_token == initial.fencing_token + 1
        assert second.owner_run_id
    finally:
        restarted.close()
