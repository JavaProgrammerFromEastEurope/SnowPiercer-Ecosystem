import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptStatus,
)


class _CommitThenRaiseOnce:
    """Persist the lease renewal but lose the caller's COMMIT acknowledgement."""

    def __init__(self, connection):
        self.connection = connection
        self.raise_once = True

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        if self.raise_once:
            self.raise_once = False
            raise sqlite3.OperationalError("simulated lost lease COMMIT acknowledgement")


class _RaiseBeforeCommitOnce:
    def __init__(self, connection):
        self.connection = connection
        self.raise_once = True

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        if self.raise_once:
            self.raise_once = False
            raise sqlite3.OperationalError("simulated lease pre-commit failure")
        self.connection.commit()


def _start(store, key="lease-key"):
    return store.begin_attempt(key, "stage115 lease test", lease_seconds=600)


def test_renew_lease_resolves_lost_commit_ack_from_fresh_connection(tmp_path):
    database = tmp_path / "lease-ambiguous.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    started = _start(store)
    original_expiry = started.lease_expires_at
    raw = store._connection
    store._connection = _CommitThenRaiseOnce(raw)

    renewed = store.renew_lease(
        started.attempt_key, owner_run_id=started.owner_run_id,
        fencing_token=started.fencing_token, lease_seconds=1200,
    )

    assert renewed.status is RecoveryAttemptStatus.IN_PROGRESS
    assert renewed.owner_run_id == started.owner_run_id
    assert renewed.fencing_token == started.fencing_token
    assert renewed.lease_expires_at != original_expiry
    store._connection = raw
    store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    assert restarted.get(started.attempt_key) == renewed
    restarted.close()


def test_renew_lease_precommit_error_leaves_durable_lease_unchanged(tmp_path):
    database = tmp_path / "lease-precommit.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    started = _start(store)
    raw = store._connection
    store._connection = _RaiseBeforeCommitOnce(raw)

    # The resolver sees the original durable row, so the commit exception is preserved.
    with pytest.raises(sqlite3.OperationalError, match="pre-commit failure"):
        store.renew_lease(
            started.attempt_key, owner_run_id=started.owner_run_id,
            fencing_token=started.fencing_token, lease_seconds=1200,
        )
    assert not raw.in_transaction
    assert store.get(started.attempt_key) == started

    store._connection = raw
    retried = store.renew_lease(
        started.attempt_key, owner_run_id=started.owner_run_id,
        fencing_token=started.fencing_token, lease_seconds=1200,
    )
    assert retried.lease_expires_at != started.lease_expires_at
    store.close()


def test_renew_lease_trigger_abort_does_not_poison_connection(tmp_path):
    database = tmp_path / "lease-trigger.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    started = _start(store)
    store._connection.execute("""
        CREATE TRIGGER reject_lease_update BEFORE UPDATE OF lease_expires_at ON recovery_attempts
        BEGIN SELECT RAISE(ABORT, 'lease update rejected'); END
    """)
    store._connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="lease update rejected"):
        store.renew_lease(
            started.attempt_key, owner_run_id=started.owner_run_id,
            fencing_token=started.fencing_token, lease_seconds=1200,
        )
    assert not store._connection.in_transaction
    assert store.get(started.attempt_key) == started

    store._connection.execute("DROP TRIGGER reject_lease_update")
    store._connection.commit()
    renewed = store.renew_lease(
        started.attempt_key, owner_run_id=started.owner_run_id,
        fencing_token=started.fencing_token, lease_seconds=1200,
    )
    assert renewed.lease_expires_at != started.lease_expires_at
    store.close()
