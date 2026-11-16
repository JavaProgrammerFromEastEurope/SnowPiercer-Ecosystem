"""Process-crash and competing-owner regressions for recovery attempt creation."""
from multiprocessing import get_context
import os

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def _create_then_crash(database_path, sender):
    store = EventLogRecoveryAttemptStore(database_path)
    attempt = store.begin_attempt("crash-window", "owner before abrupt exit")
    sender.send((attempt.owner_run_id, attempt.fencing_token, attempt.attempt_count))
    sender.close()
    # Deliberately bypass close()/finally to simulate process death after durable begin.
    os._exit(0)


def _retry_owner(database_path, ready, release):
    store = EventLogRecoveryAttemptStore(database_path)
    attempt = store.begin_attempt("race-key", "authorized concurrent retry")
    ready.put((attempt.owner_run_id, attempt.fencing_token, attempt.attempt_count))
    if not release.wait(timeout=10):
        os._exit(3)
    store.finish_success(
        "race-key", owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token,
    )
    store.close()


def test_real_process_crash_requires_authorization_before_new_fenced_attempt(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "crash.sqlite")
    receiver, sender = context.Pipe(duplex=False)
    owner = context.Process(target=_create_then_crash, args=(database, sender))
    owner.start()
    sender.close()
    first_owner, first_fence, first_count = receiver.recv()
    receiver.close()
    owner.join(timeout=10)
    assert owner.exitcode == 0
    assert first_owner and first_fence == 1 and first_count == 1

    store = EventLogRecoveryAttemptStore(database)
    with pytest.raises(RecoveryAttemptBlocked, match="authorize retry explicitly"):
        store.begin_attempt("crash-window", "restart detects crashed owner")
    failed = store.get("crash-window")
    assert failed.status is RecoveryAttemptStatus.FAILED
    assert failed.attempt_count == 1
    assert failed.owner_pid is None
    assert failed.owner_run_id == first_owner
    assert failed.fencing_token == first_fence

    store.authorize_retry("crash-window", operator="reviewer", reason="crash state reviewed")
    second = store.begin_attempt("crash-window", "explicitly authorized recovery")
    assert second.status is RecoveryAttemptStatus.IN_PROGRESS
    assert second.attempt_count == 2
    assert second.fencing_token == first_fence + 1
    assert second.owner_run_id != first_owner
    store.finish_failure(
        "crash-window", "test cleanup", owner_run_id=second.owner_run_id,
        fencing_token=second.fencing_token,
    )
    store.close()


def test_two_processes_cannot_claim_the_same_authorized_retry(tmp_path):
    context = get_context("spawn")
    database = str(tmp_path / "race.sqlite")
    setup = EventLogRecoveryAttemptStore(database)
    first = setup.begin_attempt("race-key", "initial attempt")
    setup.finish_failure(
        "race-key", "injected initial failure", owner_run_id=first.owner_run_id,
        fencing_token=first.fencing_token,
    )
    setup.authorize_retry("race-key", operator="reviewer", reason="retry reviewed")
    setup.close()

    ready = context.Queue()
    release = context.Event()
    winner = context.Process(target=_retry_owner, args=(database, ready, release))
    winner.start()
    state = ready.get(timeout=10)
    assert state[1:] == (first.fencing_token + 1, 2)

    competitor = EventLogRecoveryAttemptStore(database)
    try:
        with pytest.raises(RecoveryAttemptBlocked, match="another live process"):
            competitor.begin_attempt("race-key", "competing authorized retry")
        durable = competitor.get("race-key")
        assert durable.status is RecoveryAttemptStatus.IN_PROGRESS
        assert durable.attempt_count == 2
        assert durable.fencing_token == first.fencing_token + 1
        assert durable.owner_run_id == state[0]
    finally:
        competitor.close()
        release.set()
        winner.join(timeout=10)
        if winner.is_alive():
            winner.terminate()
            winner.join(timeout=5)
    assert winner.exitcode == 0

    check = EventLogRecoveryAttemptStore(database)
    final = check.get("race-key")
    assert final.status is RecoveryAttemptStatus.SUCCEEDED
    assert final.attempt_count == 2
    assert final.fencing_token == first.fencing_token + 1
    check.close()
