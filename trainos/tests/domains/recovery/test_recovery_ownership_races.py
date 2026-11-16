from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _begin(store, key="race"):
    return store.begin_attempt(key, "stage106 ownership race", lease_seconds=30)


def test_stale_owner_cannot_finish_after_authorized_retry_changes_fence(tmp_path):
    path = tmp_path / "attempts.sqlite"
    first_store = EventLogRecoveryAttemptStore(path)
    second_store = EventLogRecoveryAttemptStore(path)
    old = _begin(first_store)
    first_store.finish_failure(
        old.attempt_key, "simulated failure", owner_run_id=old.owner_run_id,
        fencing_token=old.fencing_token,
    )
    first_store.authorize_retry(old.attempt_key, operator="test-operator", reason="retry reviewed")
    current = first_store.begin_attempt(old.attempt_key, "authorized retry", lease_seconds=30)

    assert current.fencing_token == old.fencing_token + 1
    assert current.owner_run_id != old.owner_run_id
    with pytest.raises(RecoveryAttemptBlocked, match="stale recovery owner"):
        second_store.finish_success(
            old.attempt_key, owner_run_id=old.owner_run_id, fencing_token=old.fencing_token,
        )
    observed = second_store.get(old.attempt_key)
    assert observed.status is RecoveryAttemptStatus.IN_PROGRESS
    assert observed.owner_run_id == current.owner_run_id
    assert observed.fencing_token == current.fencing_token

    first_store.close()
    second_store.close()


def test_finish_and_heartbeat_race_is_serialized_across_connections(tmp_path):
    path = tmp_path / "attempts.sqlite"
    owner_store = EventLogRecoveryAttemptStore(path)
    heartbeat_store = EventLogRecoveryAttemptStore(path)
    attempt = _begin(owner_store, "finish-heartbeat-race")
    barrier = Barrier(2)

    def renew():
        barrier.wait(timeout=2)
        try:
            heartbeat_store.renew_lease(
                attempt.attempt_key, owner_run_id=attempt.owner_run_id,
                fencing_token=attempt.fencing_token, lease_seconds=30,
            )
            return "renewed"
        except RecoveryAttemptBlocked:
            return "blocked"

    def finish():
        barrier.wait(timeout=2)
        try:
            owner_store.finish_success(
                attempt.attempt_key, owner_run_id=attempt.owner_run_id,
                fencing_token=attempt.fencing_token,
            )
            return "finished"
        except RecoveryAttemptBlocked:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        renew_future = pool.submit(renew)
        finish_future = pool.submit(finish)
        renew_result = renew_future.result(timeout=5)
        finish_result = finish_future.result(timeout=5)

    final = owner_store.get(attempt.attempt_key)
    assert final.status is RecoveryAttemptStatus.SUCCEEDED
    assert final.owner_run_id is None
    assert final.lease_expires_at is None
    assert renew_result in {"renewed", "blocked"}
    assert finish_result == "finished"
    assert renew_result == "blocked" or renew_result == "renewed"

    owner_store.close()
    heartbeat_store.close()


def test_live_owner_cannot_finish_after_lease_expiry(tmp_path):
    path = tmp_path / "attempts.sqlite"
    store = EventLogRecoveryAttemptStore(path)
    attempt = _begin(store, "expired-live-owner")
    with store._lock:
        store._connection.execute(
            "UPDATE recovery_attempts SET lease_expires_at=? WHERE attempt_key=?",
            (datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat(), attempt.attempt_key),
        )
        store._connection.commit()

    with pytest.raises(RecoveryAttemptBlocked, match="lease expired while owner is still alive"):
        store.finish_success(
            attempt.attempt_key, owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token,
        )
    current = store.get(attempt.attempt_key)
    assert current.status is RecoveryAttemptStatus.IN_PROGRESS
    assert current.owner_run_id == attempt.owner_run_id
    assert current.fencing_token == attempt.fencing_token
    store.close()
