"""Expired lease recovery stays fail-closed under live-owner and retry races."""
from __future__ import annotations
from contextlib import closing

from multiprocessing import get_context
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _expired_owner(database: str, ready, continue_event, done):
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("expired-race", "owner process for expired lease", lease_seconds=300)
    ready.put((attempt.owner_run_id, attempt.fencing_token, attempt.owner_pid, attempt.attempt_count))
    if not continue_event.wait(timeout=10):
        store.close()
        return
    outcomes = []
    for action in ("renew", "finish"):
        try:
            if action == "renew":
                store.renew_lease(
                    "expired-race", owner_run_id=attempt.owner_run_id,
                    fencing_token=attempt.fencing_token, lease_seconds=300,
                )
            else:
                store.finish_success(
                    "expired-race", owner_run_id=attempt.owner_run_id,
                    fencing_token=attempt.fencing_token,
                )
            outcomes.append((action, "unexpected_success"))
        except RecoveryAttemptBlocked as exc:
            outcomes.append((action, str(exc)))
    done.put(outcomes)
    store.close()


def _claim_authorized_retry(database: str, barrier, results):
    store = EventLogRecoveryAttemptStore(database)
    barrier.wait(timeout=10)
    try:
        attempt = store.begin_attempt("expired-race", "competing authorized retry")
        results.put(("claimed", attempt.owner_run_id, attempt.fencing_token, attempt.attempt_count))
        # Keep ownership live briefly while the competitor checks durable state.
        import time
        time.sleep(0.2)
        store.finish_success(
            "expired-race", owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token,
        )
    except RecoveryAttemptBlocked as exc:
        results.put(("blocked", str(exc)))
    finally:
        store.close()


def test_expired_lease_cannot_be_resurrected_and_only_one_retry_owner_wins(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "expired-lease-contention.sqlite")
    ready, continue_event, done = context.Queue(), context.Event(), context.Queue()
    owner = context.Process(target=_expired_owner, args=(database, ready, continue_event, done))
    owner.start()
    owner_state = ready.get(timeout=10)
    owner_run_id, fencing_token, owner_pid, attempt_count = owner_state
    assert owner_pid == owner.pid
    assert fencing_token == 1 and attempt_count == 1

    # Force an already-expired lease durably while the recorded owner is still alive.
    with closing(sqlite3.connect(database)) as connection, connection:
        expired = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        connection.execute(
            "UPDATE recovery_attempts SET lease_expires_at=? WHERE attempt_key=?",
            (expired, "expired-race"),
        )

    observer = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match="another live process"):
            observer.begin_attempt("expired-race", "must not steal live owner")
    finally:
        observer.close()

    continue_event.set()
    outcomes = done.get(timeout=10)
    assert owner.is_alive() or owner.exitcode == 0
    assert {item[0] for item in outcomes} == {"renew", "finish"}
    assert all("expired" in item[1] for item in outcomes)
    owner.join(timeout=10)
    if owner.is_alive():
        owner.terminate()
        owner.join(timeout=5)
    assert owner.exitcode == 0

    journal = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match="interrupted"):
            journal.begin_attempt("expired-race", "detect dead expired owner")
        failed = journal.get("expired-race")
        assert failed.status is RecoveryAttemptStatus.FAILED
        assert failed.owner_pid is None
        assert failed.fencing_token == fencing_token
        journal.authorize_retry(
            "expired-race", operator="stage118-test", reason="reviewed expired lease and dead owner",
        )
    finally:
        journal.close()

    barrier, results = context.Barrier(2), context.Queue()
    contenders = [
        context.Process(target=_claim_authorized_retry, args=(database, barrier, results))
        for _ in range(2)
    ]
    for process in contenders:
        process.start()
    for process in contenders:
        process.join(timeout=15)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert all(process.exitcode == 0 for process in contenders)
    outcomes = [results.get(timeout=3) for _ in range(2)]
    assert sum(item[0] == "claimed" for item in outcomes) == 1, outcomes
    assert sum(item[0] == "blocked" for item in outcomes) == 1, outcomes

    final_store = EventLogRecoveryAttemptStore(database)
    try:
        final = final_store.get("expired-race")
        assert final.status is RecoveryAttemptStatus.SUCCEEDED
        assert final.attempt_count == 2
        assert final.fencing_token == fencing_token + 1
        assert final.owner_run_id is None
        assert final.lease_expires_at is None
    finally:
        final_store.close()
