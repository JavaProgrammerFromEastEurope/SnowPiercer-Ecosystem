from contextlib import closing
"""Stage 104: lease renewal and completion remain fenced and transactional."""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from kernel.command.events import EventLogRecoveryAttemptStore, RecoveryAttemptBlocked, RecoveryAttemptStatus


def test_owner_can_renew_lease_without_changing_fencing_token(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "journal.sqlite")
    attempt = journal.begin_attempt("lease-renew", "test renewal", lease_seconds=30)

    renewed = journal.renew_lease(
        "lease-renew", owner_run_id=attempt.owner_run_id,
        fencing_token=attempt.fencing_token, lease_seconds=60,
    )

    assert renewed.status is RecoveryAttemptStatus.IN_PROGRESS
    assert renewed.owner_run_id == attempt.owner_run_id
    assert renewed.fencing_token == attempt.fencing_token
    assert datetime.fromisoformat(renewed.lease_expires_at) > datetime.fromisoformat(attempt.lease_expires_at)
    journal.close()


def test_stale_owner_cannot_renew_current_lease(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "journal.sqlite")
    attempt = journal.begin_attempt("lease-stale", "test stale renewal")

    with pytest.raises(RecoveryAttemptBlocked, match="stale recovery owner"):
        journal.renew_lease(
            "lease-stale", owner_run_id="not-the-owner",
            fencing_token=attempt.fencing_token, lease_seconds=60,
        )

    current = journal.get("lease-stale")
    assert current.owner_run_id == attempt.owner_run_id
    assert current.fencing_token == attempt.fencing_token
    assert current.lease_expires_at == attempt.lease_expires_at
    journal.close()


def test_expired_lease_cannot_be_renewed_or_finished_by_live_owner(tmp_path, monkeypatch):
    journal = EventLogRecoveryAttemptStore(tmp_path / "journal.sqlite")
    attempt = journal.begin_attempt("lease-expired", "test expired lease")
    expired = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    with closing(sqlite3.connect(journal.database_path)) as connection, connection:
        connection.execute(
            "UPDATE recovery_attempts SET lease_expires_at=? WHERE attempt_key=?",
            (expired, "lease-expired"),
        )
    monkeypatch.setattr(EventLogRecoveryAttemptStore, "_pid_is_alive", staticmethod(lambda _pid: True))

    with pytest.raises(RecoveryAttemptBlocked, match="lease expired"):
        journal.renew_lease(
            "lease-expired", owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token,
        )
    with pytest.raises(RecoveryAttemptBlocked, match="lease expired"):
        journal.finish_success(
            "lease-expired", owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token,
        )

    current = journal.get("lease-expired")
    assert current.status is RecoveryAttemptStatus.IN_PROGRESS
    assert current.owner_run_id == attempt.owner_run_id
    assert current.fencing_token == attempt.fencing_token
    journal.close()


def test_lease_duration_validation_rejects_non_finite_and_out_of_range(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "journal.sqlite")
    for value in (0, -1, float("nan"), float("inf"), 86401, True):
        with pytest.raises(ValueError, match="lease_seconds"):
            journal.begin_attempt(f"invalid-{str(value)}", "invalid lease", lease_seconds=value)
    journal.close()


def test_lease_renewal_is_visible_across_independent_store_connections(tmp_path):
    path = tmp_path / "shared-journal.sqlite"
    owner_store = EventLogRecoveryAttemptStore(path)
    other_store = EventLogRecoveryAttemptStore(path)
    attempt = owner_store.begin_attempt("multi-connection", "cross-connection renewal")

    renewed = other_store.renew_lease(
        "multi-connection", owner_run_id=attempt.owner_run_id,
        fencing_token=attempt.fencing_token, lease_seconds=120,
    )
    assert owner_store.get("multi-connection").lease_expires_at == renewed.lease_expires_at

    owner_store.finish_success(
        "multi-connection", owner_run_id=attempt.owner_run_id,
        fencing_token=attempt.fencing_token,
    )
    with pytest.raises(RecoveryAttemptBlocked, match="stale recovery owner"):
        other_store.renew_lease(
            "multi-connection", owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token,
        )
    assert owner_store.get("multi-connection").status is RecoveryAttemptStatus.SUCCEEDED
    owner_store.close()
    other_store.close()
