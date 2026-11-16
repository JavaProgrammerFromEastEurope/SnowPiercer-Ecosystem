"""Cross-process races around ambiguous COMMIT acknowledgements."""
from multiprocessing import get_context
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _CommitThenPauseAndRaise:
    """Commit durably, let another process observe it, then lose the acknowledgement."""
    def __init__(self, connection, committed, release):
        self._connection = connection
        self._committed = committed
        self._release = release
        self._first = True

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def commit(self):
        self._connection.commit()
        if self._first:
            self._first = False
            self._committed.set()
            if not self._release.wait(timeout=10):
                raise RuntimeError("test timed out waiting to release ambiguous COMMIT")
            raise sqlite3.OperationalError("simulated lost COMMIT acknowledgement")


def _finish_with_lost_ack(database, owner_id, fence, committed, release, results):
    store = EventLogRecoveryAttemptStore(database)
    raw = store._connection
    store._connection = _CommitThenPauseAndRaise(raw, committed, release)
    try:
        result = store.finish_success(
            "ambiguous-race", owner_run_id=owner_id, fencing_token=fence,
        )
        results.put(("returned", result.status.value, result.owner_run_id, result.lease_expires_at))
    except BaseException as exc:
        results.put(("raised", type(exc).__name__, str(exc)))
    finally:
        store._connection = raw
        store.close()


def test_competing_process_cannot_overwrite_terminal_row_during_lost_commit_ack(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "cross-process-ambiguous.sqlite")
    setup = EventLogRecoveryAttemptStore(database)
    initial = setup.begin_attempt("ambiguous-race", "race finish against lost acknowledgement")
    setup.close()

    committed = context.Event()
    release = context.Event()
    results = context.Queue()
    finisher = context.Process(
        target=_finish_with_lost_ack,
        args=(database, initial.owner_run_id, initial.fencing_token, committed, release, results),
    )
    finisher.start()
    try:
        assert committed.wait(timeout=10), "finisher did not reach durable COMMIT"
        competitor = EventLogRecoveryAttemptStore(database)
        try:
            durable = competitor.get("ambiguous-race")
            assert durable is not None
            assert durable.status is RecoveryAttemptStatus.SUCCEEDED
            assert durable.owner_run_id is None
            assert durable.lease_expires_at is None
            with pytest.raises(RecoveryAttemptBlocked, match="no in-progress"):
                competitor.finish_failure(
                    "ambiguous-race", "competing failure",
                    owner_run_id=initial.owner_run_id,
                    fencing_token=initial.fencing_token,
                )
            # A competing connection cannot alter the committed terminal transition.
            assert competitor.get("ambiguous-race").status is RecoveryAttemptStatus.SUCCEEDED
        finally:
            competitor.close()
    finally:
        release.set()
        finisher.join(timeout=15)
        if finisher.is_alive():
            finisher.terminate()
            finisher.join(timeout=5)

    assert finisher.exitcode == 0
    outcome = results.get(timeout=3)
    assert outcome == ("returned", RecoveryAttemptStatus.SUCCEEDED.value, None, None)

    check = EventLogRecoveryAttemptStore(database)
    try:
        final = check.get("ambiguous-race")
        assert final is not None
        assert final.status is RecoveryAttemptStatus.SUCCEEDED
        assert final.attempt_count == 1
        assert final.fencing_token == initial.fencing_token
        assert final.owner_run_id is None
        assert final.lease_expires_at is None
    finally:
        check.close()


def _authorize_retry(database, ready, start, results, operator):
    store = EventLogRecoveryAttemptStore(database)
    ready.put(operator)
    if not start.wait(timeout=10):
        results.put((operator, "timeout"))
        store.close()
        return
    try:
        attempt = store.authorize_retry(
            "retry-race", operator=operator, reason=f"reviewed by {operator}",
        )
        results.put((operator, "authorized", attempt.status.value, attempt.authorized_by))
    except RecoveryAttemptBlocked as exc:
        results.put((operator, "blocked", str(exc)))
    finally:
        store.close()


def test_two_processes_racing_retry_authorization_have_one_durable_winner(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "retry-authorization-race.sqlite")
    setup = EventLogRecoveryAttemptStore(database)
    initial = setup.begin_attempt("retry-race", "prepare retry authorization race")
    setup.finish_failure(
        "retry-race", "controlled failure", owner_run_id=initial.owner_run_id,
        fencing_token=initial.fencing_token,
    )
    setup.close()

    ready = context.Queue()
    start = context.Event()
    results = context.Queue()
    processes = [
        context.Process(target=_authorize_retry,
                        args=(database, ready, start, results, operator))
        for operator in ("reviewer-a", "reviewer-b")
    ]
    for process in processes:
        process.start()
    try:
        assert {ready.get(timeout=10), ready.get(timeout=10)} == {"reviewer-a", "reviewer-b"}
        start.set()
        outcomes = [results.get(timeout=10), results.get(timeout=10)]
    finally:
        start.set()
        for process in processes:
            process.join(timeout=15)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
    assert all(process.exitcode == 0 for process in processes)
    assert sum(item[1] == "authorized" for item in outcomes) == 1
    assert sum(item[1] == "blocked" for item in outcomes) == 1

    winner = next(item[0] for item in outcomes if item[1] == "authorized")
    check = EventLogRecoveryAttemptStore(database)
    try:
        final = check.get("retry-race")
        assert final is not None
        assert final.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        assert final.authorized_by == winner
        assert final.authorization_reason == f"reviewed by {winner}"
        assert final.attempt_count == initial.attempt_count
        assert final.fencing_token == initial.fencing_token
    finally:
        check.close()
