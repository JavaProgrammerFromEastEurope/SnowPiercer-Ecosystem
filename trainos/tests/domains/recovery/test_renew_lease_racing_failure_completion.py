"""Lease renewal racing terminal failure must preserve one durable outcome."""
from multiprocessing import get_context

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _renew(database, owner_run_id, fencing_token, barrier, results):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            attempt = store.renew_lease(
                "renew-failure-race", owner_run_id=owner_run_id,
                fencing_token=fencing_token, lease_seconds=600,
            )
            results.put(("renewed", attempt.status.value, attempt.owner_run_id,
                         attempt.fencing_token, attempt.lease_expires_at is not None))
        except RecoveryAttemptBlocked as exc:
            results.put(("renew_blocked", str(exc)))
    except BaseException as exc:
        results.put(("error", repr(exc)))
        raise
    finally:
        store.close()


def _fail(database, owner_run_id, fencing_token, barrier, results):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            attempt = store.finish_failure(
                "renew-failure-race", "recovery candidate validation failed",
                owner_run_id=owner_run_id, fencing_token=fencing_token,
            )
            results.put(("failed", attempt.status.value, attempt.last_error,
                         attempt.owner_run_id, attempt.lease_expires_at,
                         attempt.fencing_token))
        except RecoveryAttemptBlocked as exc:
            results.put(("finish_blocked", str(exc)))
    except BaseException as exc:
        results.put(("error", repr(exc)))
        raise
    finally:
        store.close()


def test_lease_renewal_racing_failure_completion_has_one_durable_failure(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "renew-failure-race.sqlite")
    setup = EventLogRecoveryAttemptStore(database)
    initial = setup.begin_attempt("renew-failure-race", "concurrent renewal and failure")
    setup.close()

    barrier = context.Barrier(2)
    results = context.Queue()
    workers = [
        context.Process(target=_renew, args=(database, initial.owner_run_id,
                                             initial.fencing_token, barrier, results)),
        context.Process(target=_fail, args=(database, initial.owner_run_id,
                                            initial.fencing_token, barrier, results)),
    ]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)
        assert all(not worker.is_alive() for worker in workers)
        assert [worker.exitcode for worker in workers] == [0, 0]
        outcomes = [results.get(timeout=5) for _ in workers]
        assert all(outcome[0] != "error" for outcome in outcomes), outcomes
        assert sum(outcome[0] == "failed" for outcome in outcomes) == 1, outcomes
        assert sum(outcome[0] in ("renewed", "renew_blocked") for outcome in outcomes) == 1, outcomes
        assert {outcome[0] for outcome in outcomes} in (
            {"renewed", "failed"}, {"renew_blocked", "failed"},
        )

        store = EventLogRecoveryAttemptStore(database)
        try:
            final = store.get("renew-failure-race")
            assert final is not None
            assert final.status is RecoveryAttemptStatus.FAILED
            assert final.attempt_count == 1
            assert final.fencing_token == initial.fencing_token
            assert final.last_error == "recovery candidate validation failed"
            assert final.owner_run_id is None
            assert final.lease_expires_at is None
            assert final.owner_pid is None
            # A late renewal cannot resurrect a terminal attempt.
            before = final
            try:
                store.renew_lease(
                    "renew-failure-race", owner_run_id=initial.owner_run_id,
                    fencing_token=initial.fencing_token,
                )
            except RecoveryAttemptBlocked:
                pass
            else:
                raise AssertionError("terminal recovery attempt unexpectedly renewed")
            assert store.get("renew-failure-race") == before
        finally:
            store.close()
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        results.close()
        results.join_thread()
