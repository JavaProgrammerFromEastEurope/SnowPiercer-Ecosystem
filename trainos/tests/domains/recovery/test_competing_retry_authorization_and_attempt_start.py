"""A single durable retry authorization can be consumed by only one contender."""
from multiprocessing import get_context

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _authorize(database, barrier, result_queue, operator):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            result = store.authorize_retry(
                "single-use-retry", operator=operator, reason=f"reviewed by {operator}",
            )
        except RecoveryAttemptBlocked as exc:
            result_queue.put((operator, "blocked", str(exc)))
        else:
            result_queue.put((operator, "authorized", result.status.value))
    except BaseException as exc:
        result_queue.put((operator, "error", repr(exc)))
        raise
    finally:
        store.close()


def _start(database, barrier, result_queue, contender):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            result = store.begin_attempt("single-use-retry", f"start requested by {contender}")
        except RecoveryAttemptBlocked as exc:
            result_queue.put((contender, "blocked", str(exc)))
        else:
            result_queue.put((contender, "started", result.owner_run_id, result.fencing_token))
    except BaseException as exc:
        result_queue.put((contender, "error", repr(exc)))
        raise
    finally:
        store.close()


def _run_race(context, database, worker_specs):
    barrier = context.Barrier(len(worker_specs))
    result_queue = context.Queue()
    workers = [context.Process(target=target, args=(database, barrier, result_queue, name))
               for target, name in worker_specs]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)
        assert all(not worker.is_alive() for worker in workers)
        assert [worker.exitcode for worker in workers] == [0] * len(workers)
        results = [result_queue.get(timeout=5) for _ in workers]
        assert len({result[0] for result in results}) == len(worker_specs), results
        assert all(result[1] != "error" for result in results), results
        return results
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        result_queue.close()
        result_queue.join_thread()


def test_competing_authorizations_and_starters_consume_one_retry_once(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "single-use-retry.sqlite")
    store = EventLogRecoveryAttemptStore(database)
    try:
        first = store.begin_attempt("single-use-retry", "initial recovery", max_attempts=3)
        failed = store.finish_failure(
            first.attempt_key, "initial recovery failed", owner_run_id=first.owner_run_id,
            fencing_token=first.fencing_token,
        )
        assert failed.status is RecoveryAttemptStatus.FAILED
        assert failed.attempt_count == 1
        assert failed.fencing_token == 1
    finally:
        store.close()

    authorization_results = _run_race(context, database, [
        (_authorize, "operator-a"), (_authorize, "operator-b"),
    ])
    assert sorted(result[1] for result in authorization_results) == ["authorized", "blocked"], authorization_results
    authorized_result = next(result for result in authorization_results if result[1] == "authorized")
    assert authorized_result[2] == RecoveryAttemptStatus.RETRY_AUTHORIZED.value
    blocked_authorization = next(result for result in authorization_results if result[1] == "blocked")
    assert "retry can only be authorized for a failed attempt" in blocked_authorization[2]

    after_authorization = EventLogRecoveryAttemptStore(database)
    try:
        authorized = after_authorization.get("single-use-retry")
        assert authorized is not None
        assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        assert authorized.attempt_count == 1
        assert authorized.fencing_token == 1
        assert authorized.authorized_by == authorized_result[0]
        assert authorized.authorization_reason == f"reviewed by {authorized_result[0]}"
    finally:
        after_authorization.close()

    start_results = _run_race(context, database, [
        (_start, "starter-a"), (_start, "starter-b"),
    ])
    assert sorted(result[1] for result in start_results) == ["blocked", "started"], start_results
    started = next(result for result in start_results if result[1] == "started")
    blocked_start = next(result for result in start_results if result[1] == "blocked")
    assert "already in progress" in blocked_start[2]

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        current = reopened.get("single-use-retry")
        assert current is not None
        assert current.status is RecoveryAttemptStatus.IN_PROGRESS
        assert current.attempt_count == 2
        assert current.max_attempts == 3
        assert current.fencing_token == 2
        assert current.owner_run_id == started[2]
        assert current.owner_run_id not in (None, first.owner_run_id)
        assert current.owner_pid is not None
        assert current.lease_expires_at is not None
        assert current.authorized_by is None
        assert current.authorization_reason is None
        assert current.last_error is None

        # The same authorization has been consumed; a duplicate operator request
        # cannot reuse it or alter the active journal row. The race above verifies
        # that a competing starter is blocked while the winning owner is live.
        with pytest.raises(RecoveryAttemptBlocked, match="retry can only be authorized"):
            reopened.authorize_retry(
                "single-use-retry", operator="late-operator", reason="duplicate authorization",
            )
        unchanged = reopened.get("single-use-retry")
        assert unchanged == current
    finally:
        reopened.close()
