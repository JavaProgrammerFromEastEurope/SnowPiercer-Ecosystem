"""A lost authorization acknowledgement must still yield one retry start only."""
from multiprocessing import get_context
import sqlite3
import pytest
from kernel.command.events import EventLogRecoveryAttemptStore, RecoveryAttemptBlocked, RecoveryAttemptStatus

class _CommitThenLoseAcknowledgement:
    """Persist the transaction, then simulate a lost COMMIT acknowledgement."""
    def __init__(self, connection):
        self.connection = connection
        self.raised = False
    def __getattr__(self, name):
        return getattr(self.connection, name)
    def commit(self):
        self.connection.commit()
        if not self.raised:
            self.raised = True
            raise sqlite3.OperationalError("simulated lost COMMIT acknowledgement")

def _consume_authorization(database, barrier, result_queue, name):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            attempt = store.begin_attempt("stage142-key", f"consumer {name}", max_attempts=3)
        except RecoveryAttemptBlocked as exc:
            result_queue.put((name, "blocked", str(exc)))
        else:
            result_queue.put((name, "started", attempt.owner_run_id, attempt.fencing_token))
    except BaseException as exc:
        result_queue.put((name, "error", repr(exc)))
        raise
    finally:
        store.close()

def test_lost_authorization_ack_with_competing_consumers_starts_exactly_one_retry(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "ambiguous-authorization-consumers.sqlite")
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt("stage142-key", "initial attempt", max_attempts=3)
    failed = store.finish_failure(first.attempt_key, "controlled failure", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token)
    raw_connection = store._connection
    proxy = _CommitThenLoseAcknowledgement(raw_connection)
    store._connection = proxy
    authorized = store.authorize_retry(first.attempt_key, operator="stage142-reviewer", reason="retry reviewed")
    assert proxy.raised
    assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    assert authorized.attempt_count == failed.attempt_count == 1
    assert authorized.authorized_by == "stage142-reviewer"
    store._connection = raw_connection
    store.close()

    barrier = context.Barrier(2)
    result_queue = context.Queue()
    workers = [context.Process(target=_consume_authorization, args=(database, barrier, result_queue, name)) for name in ("consumer-a", "consumer-b")]
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join(timeout=20)
        assert all(not worker.is_alive() for worker in workers), "consumer process timed out"
        assert [worker.exitcode for worker in workers] == [0, 0]
        results = [result_queue.get(timeout=5) for _ in workers]
        assert {item[0] for item in results} == {"consumer-a", "consumer-b"}, results
        assert sum(item[1] == "started" for item in results) == 1, results
        assert sum(item[1] == "blocked" for item in results) == 1, results
        assert all(item[1] != "error" for item in results), results
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        result_queue.close()
        result_queue.join_thread()

    reopened = EventLogRecoveryAttemptStore(database)
    try:
        final = reopened.get("stage142-key")
        assert final is not None
        assert final.status is RecoveryAttemptStatus.IN_PROGRESS
        assert final.attempt_count == 2
        assert final.fencing_token == 2
        assert final.owner_run_id and final.owner_run_id != first.owner_run_id
        assert final.authorized_by is None
        assert final.authorization_reason is None
        with pytest.raises(RecoveryAttemptBlocked, match="already in progress|previous recovery attempt was interrupted"):
            reopened.begin_attempt("stage142-key", "duplicate retry must be blocked", max_attempts=3)
        after_duplicate = reopened.get("stage142-key")
        assert after_duplicate is not None
        assert after_duplicate.attempt_count == final.attempt_count == 2
        assert after_duplicate.fencing_token == final.fencing_token == 2
        assert after_duplicate.status in {RecoveryAttemptStatus.IN_PROGRESS, RecoveryAttemptStatus.FAILED}
    finally:
        reopened.close()
