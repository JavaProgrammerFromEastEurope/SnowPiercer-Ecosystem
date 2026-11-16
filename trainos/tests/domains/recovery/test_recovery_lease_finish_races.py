"""Lease-renewal/finish races and stale-owner fencing regressions."""
from multiprocessing import get_context
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _race_renew_finish(database, owner_run_id, fencing_token, barrier, results):
    store = EventLogRecoveryAttemptStore(database)
    barrier.wait(timeout=10)
    try:
        attempt = store.renew_lease(
            "lease-race", owner_run_id=owner_run_id,
            fencing_token=fencing_token, lease_seconds=120,
        )
        results.put(("renewed", attempt.status.value, attempt.fencing_token))
    except RecoveryAttemptBlocked as exc:
        results.put(("renew_blocked", str(exc)))
    try:
        attempt = store.finish_success(
            "lease-race", owner_run_id=owner_run_id, fencing_token=fencing_token,
        )
        results.put(("finished", attempt.status.value, attempt.fencing_token))
    except RecoveryAttemptBlocked as exc:
        results.put(("finish_blocked", str(exc)))
    finally:
        store.close()


def test_concurrent_renew_and_finish_preserve_one_terminal_transition(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "lease-finish-race.sqlite")
    setup = EventLogRecoveryAttemptStore(database)
    initial = setup.begin_attempt("lease-race", "exercise concurrent renewal and finish")
    setup.close()

    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(
            target=_race_renew_finish,
            args=(database, initial.owner_run_id, initial.fencing_token, barrier, results),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=15)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert all(process.exitcode == 0 for process in processes)
    outcomes = [results.get(timeout=3) for _ in range(4)]

    check = EventLogRecoveryAttemptStore(database)
    try:
        final = check.get("lease-race")
        assert final.status is RecoveryAttemptStatus.SUCCEEDED
        assert final.fencing_token == initial.fencing_token
        assert final.owner_run_id is None
        assert final.lease_expires_at is None
        # Only one finisher can transition the row; any renewal either commits before
        # that transition or is rejected after the terminal state becomes visible.
        assert sum(item[0] == "finished" for item in outcomes) == 1
        assert all(item[0] in {"renewed", "renew_blocked", "finished", "finish_blocked"}
                   for item in outcomes)
    finally:
        check.close()


def test_stale_owner_cannot_renew_or_finish_after_new_fence(tmp_path):
    database = tmp_path / "stale-owner.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt("fence", "first owner")
    store.finish_failure(
        "fence", "owner failed", owner_run_id=first.owner_run_id,
        fencing_token=first.fencing_token,
    )
    store.authorize_retry("fence", operator="reviewer", reason="reviewed failure")
    second = store.begin_attempt("fence", "new authorized owner")
    try:
        assert second.fencing_token == first.fencing_token + 1
        with pytest.raises(RecoveryAttemptBlocked, match="stale recovery owner"):
            store.renew_lease(
                "fence", owner_run_id=first.owner_run_id,
                fencing_token=first.fencing_token,
            )
        with pytest.raises(RecoveryAttemptBlocked, match="stale recovery owner"):
            store.finish_success(
                "fence", owner_run_id=first.owner_run_id,
                fencing_token=first.fencing_token,
            )
        durable = store.get("fence")
        assert durable.status is RecoveryAttemptStatus.IN_PROGRESS
        assert durable.owner_run_id == second.owner_run_id
        assert durable.fencing_token == second.fencing_token
        store.finish_failure(
            "fence", "test cleanup", owner_run_id=second.owner_run_id,
            fencing_token=second.fencing_token,
        )
    finally:
        store.close()


def test_lease_renewal_sqlite_trigger_failure_rolls_back_cleanly(tmp_path):
    database = tmp_path / "renew-trigger.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("trigger", "trigger failure")
    before = store.get("trigger")
    store._connection.execute("""
        CREATE TRIGGER reject_lease_renewal
        BEFORE UPDATE OF lease_expires_at ON recovery_attempts
        BEGIN SELECT RAISE(ABORT, 'injected lease update failure'); END
    """)
    store._connection.commit()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="injected lease update failure"):
            store.renew_lease(
                "trigger", owner_run_id=attempt.owner_run_id,
                fencing_token=attempt.fencing_token, lease_seconds=120,
            )
        after = store.get("trigger")
        assert after.status is before.status is RecoveryAttemptStatus.IN_PROGRESS
        assert after.lease_expires_at == before.lease_expires_at
        assert after.fencing_token == before.fencing_token
        assert not store._connection.in_transaction
        store._connection.execute("DROP TRIGGER reject_lease_renewal")
        store._connection.commit()
        renewed = store.renew_lease(
            "trigger", owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token, lease_seconds=600,
        )
        assert renewed.lease_expires_at >= before.lease_expires_at
        store.finish_failure(
            "trigger", "test cleanup", owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token,
        )
    finally:
        store.close()
