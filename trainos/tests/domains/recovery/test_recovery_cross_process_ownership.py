"""Cross-process ownership tests for the durable recovery attempt journal."""
from multiprocessing import get_context

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _live_owner(database_path, ready, release):
    journal = EventLogRecoveryAttemptStore(database_path)
    state = journal.begin_attempt("cross-process", "owner process started")
    ready.put((state.status.value, state.attempt_count, state.owner_run_id, state.fencing_token))
    if not release.wait(timeout=10):
        raise RuntimeError("test did not release owner process")
    journal.finish_success("cross-process", owner_run_id=state.owner_run_id, fencing_token=state.fencing_token)
    journal.close()


def test_second_process_cannot_mark_a_live_attempt_as_interrupted(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "attempts.sqlite")
    ready = context.Queue()
    release = context.Event()
    owner = context.Process(target=_live_owner, args=(database, ready, release))
    owner.start()
    journal = None
    try:
        ready_state = ready.get(timeout=10)
        assert ready_state[:2] == (RecoveryAttemptStatus.IN_PROGRESS.value, 1)
        journal = EventLogRecoveryAttemptStore(database)
        with pytest.raises(RecoveryAttemptBlocked, match="another live process"):
            journal.begin_attempt("cross-process", "competing process")
        state = journal.get("cross-process")
        assert state.status is RecoveryAttemptStatus.IN_PROGRESS
        assert state.attempt_count == 1
    finally:
        release.set()
        owner.join(timeout=10)
        if owner.is_alive():
            owner.terminate()
            owner.join(timeout=5)
        if journal is not None:
            journal.close()
    assert owner.exitcode == 0
    check = EventLogRecoveryAttemptStore(database)
    state = check.get("cross-process")
    assert state.status is RecoveryAttemptStatus.SUCCEEDED
    assert state.attempt_count == 1
    check.close()


def test_dead_owner_requires_explicit_retry_authorization(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    journal.begin_attempt("dead-owner", "simulated abandoned attempt")
    with journal._lock:
        journal._connection.execute(
            "UPDATE recovery_attempts SET owner_pid = ? WHERE attempt_key = ?",
            (999999999, "dead-owner"),
        )
        journal._connection.commit()
    original = journal._pid_is_alive
    journal._pid_is_alive = lambda pid: False
    with pytest.raises(RecoveryAttemptBlocked, match="authorize retry explicitly"):
        journal.begin_attempt("dead-owner", "restart observes dead owner")
    state = journal.get("dead-owner")
    assert state.status is RecoveryAttemptStatus.FAILED
    assert state.attempt_count == 1
    journal._pid_is_alive = original
    authorized = journal.authorize_retry(
        "dead-owner", operator="test-reviewer", reason="reviewed interrupted attempt"
    )
    assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    journal.close()
