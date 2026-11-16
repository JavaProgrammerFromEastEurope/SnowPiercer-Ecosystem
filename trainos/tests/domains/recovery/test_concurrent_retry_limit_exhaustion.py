"""Concurrent retry authorization/start requests cannot bypass max_attempts."""
from multiprocessing import get_context

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _race_authorize(database, barrier, result_queue, worker_id):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            result = store.authorize_retry(
                "exhausted-race", operator=f"operator-{worker_id}",
                reason="concurrent authorization at exhausted limit",
            )
        except RecoveryAttemptBlocked as exc:
            result_queue.put((worker_id, "blocked", str(exc)))
        else:
            result_queue.put((worker_id, "authorized", result.status.value))
    except BaseException as exc:
        result_queue.put((worker_id, "error", repr(exc)))
        raise
    finally:
        store.close()


def _race_begin(database, barrier, result_queue, worker_id):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            result = store.begin_attempt(
                "exhausted-race", "concurrent start at exhausted limit", max_attempts=99,
            )
        except RecoveryAttemptBlocked as exc:
            result_queue.put((worker_id, "blocked", str(exc)))
        else:
            result_queue.put((worker_id, "started", result.status.value))
    except BaseException as exc:
        result_queue.put((worker_id, "error", repr(exc)))
        raise
    finally:
        store.close()


def test_concurrent_authorize_and_begin_cannot_bypass_exhausted_limit(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "exhausted-race.sqlite")
    store = EventLogRecoveryAttemptStore(database)
    try:
        first = store.begin_attempt("exhausted-race", "only permitted attempt", max_attempts=1)
        failed = store.finish_failure(
            "exhausted-race", "attempt failed", owner_run_id=first.owner_run_id,
            fencing_token=first.fencing_token,
        )
        assert failed.status is RecoveryAttemptStatus.FAILED
        before = store.get("exhausted-race")
        assert before is not None
        before_snapshot = (
            before.status, before.attempt_count, before.max_attempts, before.owner_pid,
            before.owner_run_id, before.fencing_token, before.lease_expires_at,
            before.authorized_by, before.authorization_reason,
        )
    finally:
        store.close()

    barrier = context.Barrier(4)
    result_queue = context.Queue()
    workers = [
        context.Process(target=_race_authorize, args=(database, barrier, result_queue, "a")),
        context.Process(target=_race_authorize, args=(database, barrier, result_queue, "b")),
        context.Process(target=_race_begin, args=(database, barrier, result_queue, "c")),
        context.Process(target=_race_begin, args=(database, barrier, result_queue, "d")),
    ]
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join(timeout=20)
        assert all(not worker.is_alive() for worker in workers)
        assert [worker.exitcode for worker in workers] == [0, 0, 0, 0]
        results = [result_queue.get(timeout=5) for _ in workers]
        assert all(result[1] == "blocked" for result in results), results
        assert all("maximum recovery attempts reached" in result[2] for result in results), results
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        after = restarted.get("exhausted-race")
        assert after is not None
        after_snapshot = (
            after.status, after.attempt_count, after.max_attempts, after.owner_pid,
            after.owner_run_id, after.fencing_token, after.lease_expires_at,
            after.authorized_by, after.authorization_reason,
        )
        assert after_snapshot == before_snapshot
        assert after.status is RecoveryAttemptStatus.FAILED
        assert after.attempt_count == 1
        assert after.max_attempts == 1
        assert after.fencing_token == first.fencing_token
    finally:
        restarted.close()
        result_queue.close()
        result_queue.join_thread()
