from contextlib import closing
"""A fenced-out recovery owner cannot renew or finish its replacement's attempt."""
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def test_stale_owner_cannot_renew_or_finish_after_explicitly_authorized_takeover(tmp_path):
    database = str(tmp_path / "stale-owner-takeover.sqlite")
    old_store = EventLogRecoveryAttemptStore(database)
    try:
        old = old_store.begin_attempt("stale-owner", "first recovery", max_attempts=3)

        # Model a supervisor-confirmed dead owner with an expired lease. Keep the
        # original owner UUID/fence so stale calls can be tested after replacement.
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute(
                "UPDATE recovery_attempts SET owner_pid=?, lease_expires_at=? WHERE attempt_key=?",
                (2_000_000_000, "2000-01-01T00:00:00+00:00", "stale-owner"),
            )

        with pytest.raises(RecoveryAttemptBlocked, match="previous recovery attempt was interrupted"):
            old_store.begin_attempt("stale-owner", "reconcile abandoned attempt", max_attempts=3)

        failed = old_store.get("stale-owner")
        assert failed is not None and failed.status is RecoveryAttemptStatus.FAILED
        assert failed.attempt_count == 1 and failed.fencing_token == old.fencing_token

        old_store.authorize_retry(
            "stale-owner", operator="supervisor", reason="owner process confirmed dead",
        )
        replacement = old_store.begin_attempt("stale-owner", "approved replacement")
        assert replacement.status is RecoveryAttemptStatus.IN_PROGRESS
        assert replacement.attempt_count == 2
        assert replacement.fencing_token == old.fencing_token + 1
        assert replacement.owner_run_id not in (None, old.owner_run_id)

        before = old_store.get("stale-owner")
        assert before == replacement
        stale_operations = (
            lambda: old_store.renew_lease(
                "stale-owner", owner_run_id=old.owner_run_id,
                fencing_token=old.fencing_token,
            ),
            lambda: old_store.finish_success(
                "stale-owner", owner_run_id=old.owner_run_id,
                fencing_token=old.fencing_token,
            ),
            lambda: old_store.finish_failure(
                "stale-owner", "stale worker reported failure",
                owner_run_id=old.owner_run_id, fencing_token=old.fencing_token,
            ),
        )
        for stale_operation in stale_operations:
            with pytest.raises(RecoveryAttemptBlocked, match="stale recovery owner or fencing token"):
                stale_operation()
            # Every rejected stale operation must leave the replacement's durable
            # state unchanged, not just raise after partially mutating the row.
            assert old_store.get("stale-owner") == before
            assert not old_store._connection.in_transaction
    finally:
        old_store.close()
