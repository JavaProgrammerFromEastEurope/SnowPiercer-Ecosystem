"""Stage 101: ownership races across independent journal connections."""
import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def test_competing_connections_cannot_finish_with_stale_fencing_token(tmp_path):
    database = tmp_path / "attempts.sqlite"
    owner = EventLogRecoveryAttemptStore(database)
    contender = EventLogRecoveryAttemptStore(database)
    first = owner.begin_attempt("race", "active recovery")

    # A second connection observes the same durable run, but an old run identity
    # must not be accepted even when its caller is in the same OS process.
    with pytest.raises(RecoveryAttemptBlocked, match="stale recovery owner or fencing token"):
        contender.finish_failure(
            "race", "stale worker result", owner_run_id="not-the-owner",
            fencing_token=first.fencing_token,
        )
    state = contender.get("race")
    assert state.status is RecoveryAttemptStatus.IN_PROGRESS
    assert state.owner_run_id == first.owner_run_id

    finished = owner.finish_success(
        "race", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token,
    )
    assert finished.status is RecoveryAttemptStatus.SUCCEEDED
    owner.close()
    contender.close()


def test_failed_finish_transaction_does_not_mutate_owner_or_token(tmp_path):
    database = tmp_path / "attempts.sqlite"
    journal = EventLogRecoveryAttemptStore(database)
    attempt = journal.begin_attempt("rollback", "recovery under test")
    journal._connection.execute("""
        CREATE TRIGGER reject_success BEFORE UPDATE OF status ON recovery_attempts
        WHEN NEW.status = 'succeeded'
        BEGIN SELECT RAISE(ABORT, 'injected commit-boundary failure'); END;
    """)
    journal._connection.commit()

    with pytest.raises(Exception, match="injected commit-boundary failure"):
        journal.finish_success(
            "rollback", owner_run_id=attempt.owner_run_id,
            fencing_token=attempt.fencing_token,
        )

    state = journal.get("rollback")
    assert state.status is RecoveryAttemptStatus.IN_PROGRESS
    assert state.owner_run_id == attempt.owner_run_id
    assert state.fencing_token == attempt.fencing_token
    journal._connection.execute("DROP TRIGGER reject_success")
    journal._connection.commit()
    finished = journal.finish_success(
        "rollback", owner_run_id=attempt.owner_run_id,
        fencing_token=attempt.fencing_token,
    )
    assert finished.status is RecoveryAttemptStatus.SUCCEEDED
    journal.close()
