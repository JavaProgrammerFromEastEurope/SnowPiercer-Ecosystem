"""A worker holding an old fence cannot mutate a newer recovery attempt."""
from __future__ import annotations
from contextlib import closing

from multiprocessing import get_context
import sqlite3

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _stale_worker(database: str, ready, attempt_event, results):
    store = EventLogRecoveryAttemptStore(database)
    old = store.begin_attempt("fence-takeover", "first owner", lease_seconds=300)
    ready.put((old.owner_run_id, old.fencing_token, old.owner_pid))
    if not attempt_event.wait(timeout=15):
        store.close()
        return
    outcomes = []
    operations = (
        ("renew", lambda: store.renew_lease(
            "fence-takeover", owner_run_id=old.owner_run_id,
            fencing_token=old.fencing_token, lease_seconds=300,
        )),
        ("success", lambda: store.finish_success(
            "fence-takeover", owner_run_id=old.owner_run_id,
            fencing_token=old.fencing_token,
        )),
        ("failure", lambda: store.finish_failure(
            "fence-takeover", "stale worker failure", owner_run_id=old.owner_run_id,
            fencing_token=old.fencing_token,
        )),
    )
    for name, operation in operations:
        try:
            operation()
            outcomes.append((name, "unexpected_success"))
        except RecoveryAttemptBlocked as exc:
            outcomes.append((name, str(exc)))
    results.put(outcomes)
    store.close()


def test_old_owner_cannot_mutate_attempt_after_new_fencing_token_is_issued(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "fencing-takeover.sqlite")
    ready, attempt_event, results = context.Queue(), context.Event(), context.Queue()
    stale = context.Process(target=_stale_worker, args=(database, ready, attempt_event, results))
    stale.start()
    old_owner_id, old_token, old_pid = ready.get(timeout=10)
    assert old_pid == stale.pid
    assert old_token == 1

    # Simulate a failover supervisor declaring the recorded worker dead while that
    # worker still exists as a stale actor. This adversarial setup isolates fencing
    # correctness from same-host PID liveness checks.
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "UPDATE recovery_attempts SET owner_pid=? WHERE attempt_key=?",
            (2_000_000_000, "fence-takeover"),
        )

    recovery = EventLogRecoveryAttemptStore(database)
    try:
        try:
            recovery.begin_attempt("fence-takeover", "reconcile previous owner")
        except RecoveryAttemptBlocked as exc:
            assert "interrupted" in str(exc)
        else:
            raise AssertionError("interrupted attempt should require explicit retry authorization")
        interrupted = recovery.get("fence-takeover")
        assert interrupted is not None
        assert interrupted.status is RecoveryAttemptStatus.FAILED
        assert interrupted.owner_run_id == old_owner_id
        assert interrupted.fencing_token == old_token

        recovery.authorize_retry(
            "fence-takeover", operator="stage119-test",
            reason="verified stale-owner fencing regression",
        )
        current = recovery.begin_attempt("fence-takeover", "new fenced owner", lease_seconds=300)
        assert current.owner_run_id != old_owner_id
        assert current.fencing_token == old_token + 1
        assert current.status is RecoveryAttemptStatus.IN_PROGRESS

        attempt_event.set()
        stale_outcomes = results.get(timeout=10)
        assert {name for name, _ in stale_outcomes} == {"renew", "success", "failure"}
        assert all(message != "unexpected_success" for _, message in stale_outcomes)

        unchanged = recovery.get("fence-takeover")
        assert unchanged is not None
        assert unchanged.status is RecoveryAttemptStatus.IN_PROGRESS
        assert unchanged.owner_run_id == current.owner_run_id
        assert unchanged.fencing_token == current.fencing_token
        assert unchanged.owner_pid == current.owner_pid
        assert unchanged.lease_expires_at == current.lease_expires_at

        completed = recovery.finish_success(
            "fence-takeover", owner_run_id=current.owner_run_id,
            fencing_token=current.fencing_token,
        )
        assert completed.status is RecoveryAttemptStatus.SUCCEEDED
        assert completed.owner_run_id is None
        assert completed.owner_pid is None
        assert completed.lease_expires_at is None
        assert completed.fencing_token == old_token + 1
    finally:
        attempt_event.set()
        stale.join(timeout=10)
        if stale.is_alive():
            stale.terminate()
            stale.join(timeout=5)
        recovery.close()
    assert stale.exitcode == 0
