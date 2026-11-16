"""Stage 102: tokenless completion and obsolete retry owners fail closed."""

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def test_new_fenced_attempt_cannot_be_finished_with_pid_only_compatibility(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    attempt = journal.begin_attempt("strict", "fenced recovery")

    # Same PID is not sufficient: another coroutine/thread in this process may
    # still hold a stale reference to the previous run.
    with pytest.raises(RecoveryAttemptBlocked, match="owner_run_id and fencing_token are required"):
        journal.finish_success("strict")

    current = journal.get("strict")
    assert current.status is RecoveryAttemptStatus.IN_PROGRESS
    assert current.owner_run_id == attempt.owner_run_id
    assert current.fencing_token == attempt.fencing_token

    finished = journal.finish_success(
        "strict", owner_run_id=attempt.owner_run_id,
        fencing_token=attempt.fencing_token,
    )
    assert finished.status is RecoveryAttemptStatus.SUCCEEDED
    journal.close()


def test_old_run_cannot_finish_after_operator_authorized_retry(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    old = journal.begin_attempt("retry-fence", "initial recovery")

    # Model startup's detection that the old process died before recording a result.
    with journal._lock:
        journal._connection.execute(
            "UPDATE recovery_attempts SET status='failed', last_error='previous attempt interrupted', owner_pid=NULL, lease_expires_at=NULL, updated_at=? WHERE attempt_key=?",
            (journal._now(), "retry-fence"),
        )
        journal._connection.commit()

    journal.authorize_retry(
        "retry-fence", operator="reviewer", reason="old owner confirmed stopped",
    )
    current = journal.begin_attempt("retry-fence", "approved recovery retry")
    assert current.fencing_token == old.fencing_token + 1
    assert current.owner_run_id != old.owner_run_id

    with pytest.raises(RecoveryAttemptBlocked, match="stale recovery owner or fencing token"):
        journal.finish_success(
            "retry-fence", owner_run_id=old.owner_run_id,
            fencing_token=old.fencing_token,
        )

    state = journal.get("retry-fence")
    assert state.status is RecoveryAttemptStatus.IN_PROGRESS
    assert state.owner_run_id == current.owner_run_id
    assert state.fencing_token == current.fencing_token
    journal.finish_success(
        "retry-fence", owner_run_id=current.owner_run_id,
        fencing_token=current.fencing_token,
    )
    assert journal.get("retry-fence").status is RecoveryAttemptStatus.SUCCEEDED
    journal.close()
