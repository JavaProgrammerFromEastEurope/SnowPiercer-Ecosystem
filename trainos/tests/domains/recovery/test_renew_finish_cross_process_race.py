"""Cross-connection races between lease renewal and terminal completion."""
from multiprocessing import get_context
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _renew_worker(database, owner_run_id, fencing_token, barrier, results):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            attempt = store.renew_lease(
                "stage116-race", owner_run_id=owner_run_id,
                fencing_token=fencing_token, lease_seconds=900,
            )
            results.put(("renewed", attempt.status.value, attempt.lease_expires_at is not None))
        except RecoveryAttemptBlocked as exc:
            results.put(("renew_blocked", str(exc)))
    finally:
        store.close()


def _finish_worker(database, owner_run_id, fencing_token, barrier, results):
    store = EventLogRecoveryAttemptStore(database)
    try:
        barrier.wait(timeout=10)
        try:
            attempt = store.finish_success(
                "stage116-race", owner_run_id=owner_run_id,
                fencing_token=fencing_token,
            )
            results.put(("finished", attempt.status.value, attempt.lease_expires_at))
        except RecoveryAttemptBlocked as exc:
            results.put(("finish_blocked", str(exc)))
    finally:
        store.close()


class _CommitThenFinishThenRaise:
    """Let renewal commit, finish from another connection, then lose its ack."""

    def __init__(self, connection, database, owner_run_id, fencing_token):
        self.connection = connection
        self.database = database
        self.owner_run_id = owner_run_id
        self.fencing_token = fencing_token
        self.raised = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        if not self.raised:
            self.raised = True
            other = EventLogRecoveryAttemptStore(self.database)
            try:
                other.finish_success(
                    "stage116-ambiguous", owner_run_id=self.owner_run_id,
                    fencing_token=self.fencing_token,
                )
            finally:
                other.close()
            raise sqlite3.OperationalError("simulated lost renewal acknowledgement after competing finish")


def test_renewal_racing_finish_has_one_terminal_durable_state(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "renew-finish-race.sqlite")
    setup = EventLogRecoveryAttemptStore(database)
    initial = setup.begin_attempt("stage116-race", "renew versus finish race")
    setup.close()

    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(
            target=_renew_worker,
            args=(database, initial.owner_run_id, initial.fencing_token, barrier, results),
        ),
        context.Process(
            target=_finish_worker,
            args=(database, initial.owner_run_id, initial.fencing_token, barrier, results),
        ),
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=15)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        assert all(process.exitcode == 0 for process in processes)
        outcomes = [results.get(timeout=3) for _ in processes]
        assert {item[0] for item in outcomes} in (
            {"renewed", "finished"},
            {"renew_blocked", "finished"},
            {"renew_blocked", "finish_blocked"},
        )

        check = EventLogRecoveryAttemptStore(database)
        try:
            final = check.get("stage116-race")
            assert final.status is RecoveryAttemptStatus.SUCCEEDED
            assert final.owner_run_id is None
            assert final.lease_expires_at is None
            assert final.fencing_token == initial.fencing_token
        finally:
            check.close()
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()
        results.join_thread()


def test_ambiguous_renewal_does_not_claim_success_after_competing_finish(tmp_path):
    database = tmp_path / "renew-ambiguous-finish.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    initial = store.begin_attempt("stage116-ambiguous", "ambiguous renewal race")
    raw = store._connection
    store._connection = _CommitThenFinishThenRaise(
        raw, database, initial.owner_run_id, initial.fencing_token,
    )
    try:
        # The renewal did commit, but another valid transition superseded its exact
        # expected row before the acknowledgement was checked. The API must not report
        # an unqualified success based on a now-different durable state.
        with pytest.raises(sqlite3.OperationalError, match="competing finish"):
            store.renew_lease(
                initial.attempt_key, owner_run_id=initial.owner_run_id,
                fencing_token=initial.fencing_token, lease_seconds=1200,
            )
        assert not raw.in_transaction
    finally:
        store._connection = raw
        store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        final = restarted.get(initial.attempt_key)
        assert final.status is RecoveryAttemptStatus.SUCCEEDED
        assert final.owner_run_id is None
        assert final.lease_expires_at is None
        assert final.fencing_token == initial.fencing_token
    finally:
        restarted.close()
