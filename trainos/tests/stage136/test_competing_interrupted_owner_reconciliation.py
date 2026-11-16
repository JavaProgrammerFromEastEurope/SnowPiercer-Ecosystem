from tests.sqlite_resource_helpers import managed_sqlite_connection
"""Concurrent observers must reconcile one dead owner only once."""
from multiprocessing import get_context
import sqlite3

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _try_reconcile(database, barrier, result_queue, worker_name):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            result = store.begin_attempt(
                "dead-owner-race", f"recovery requested by {worker_name}", max_attempts=3,
            )
        except RecoveryAttemptBlocked as exc:
            result_queue.put((worker_name, "blocked", str(exc)))
        else:
            result_queue.put((worker_name, "started", result.status.value))
    except BaseException as exc:
        result_queue.put((worker_name, "error", repr(exc)))
        raise
    finally:
        store.close()


def test_two_processes_reconcile_dead_owner_once_and_neither_starts_unapproved_retry(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "dead-owner-race.sqlite")
    store = EventLogRecoveryAttemptStore(database)
    initial = store.begin_attempt("dead-owner-race", "attempt whose owner will exit", max_attempts=3)
    store.close()

    # Simulate a confirmed-dead same-host PID while preserving the original modern
    # owner UUID and fence for forensic traceability.
    with managed_sqlite_connection(database) as connection:
        connection.execute(
            "UPDATE recovery_attempts SET owner_pid=?, lease_expires_at=? WHERE attempt_key=?",
            (2_000_000_000, "2000-01-01T00:00:00+00:00", "dead-owner-race"),
        )

    barrier = context.Barrier(2)
    result_queue = context.Queue()
    workers = [
        context.Process(target=_try_reconcile, args=(database, barrier, result_queue, name))
        for name in ("reconciler-a", "reconciler-b")
    ]
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join(timeout=20)
        assert all(not worker.is_alive() for worker in workers)
        assert [worker.exitcode for worker in workers] == [0, 0]
        results = [result_queue.get(timeout=5) for _ in workers]
        assert {item[0] for item in results} == {"reconciler-a", "reconciler-b"}, results
        assert all(item[1] == "blocked" for item in results), results
        messages = [item[2] for item in results]
        assert sum("previous recovery attempt was interrupted" in msg for msg in messages) == 1, results
        assert sum("previous recovery attempt failed; authorize retry explicitly" in msg for msg in messages) == 1, results
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        result_queue.close()
        result_queue.join_thread()

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        current = reopened.get("dead-owner-race")
        assert current is not None
        assert current.status is RecoveryAttemptStatus.FAILED
        assert current.attempt_count == initial.attempt_count == 1
        assert current.max_attempts == 3
        assert current.fencing_token == initial.fencing_token
        assert current.owner_run_id == initial.owner_run_id
        assert current.owner_pid is None
        assert current.lease_expires_at is None
        assert current.authorized_by is None
        assert current.authorization_reason is None
        assert not reopened._connection.in_transaction

        # A new owner can only be created after explicit authorization.
        authorized = reopened.authorize_retry(
            "dead-owner-race", operator="reviewer", reason="confirmed process termination",
        )
        assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        retry = reopened.begin_attempt("dead-owner-race", "approved retry")
        assert retry.status is RecoveryAttemptStatus.IN_PROGRESS
        assert retry.attempt_count == 2
        assert retry.fencing_token == initial.fencing_token + 1
        assert retry.owner_run_id not in (None, initial.owner_run_id)
    finally:
        reopened.close()
