from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


def test_only_one_connection_can_authorize_a_retry(tmp_path):
    database = tmp_path / "attempts.sqlite"
    setup = EventLogRecoveryAttemptStore(database)
    first = setup.begin_attempt("boot-race", "first attempt", checkpoint_fingerprint="sha256-a")
    setup.finish_failure("boot-race", "simulated failure", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token)
    setup.close()

    journals = [EventLogRecoveryAttemptStore(database) for _ in range(2)]
    barrier = Barrier(2)

    def authorize(index):
        barrier.wait(timeout=3)
        try:
            result = journals[index].authorize_retry(
                "boot-race", operator=f"operator-{index}", reason="reviewed checkpoint",
            )
            return ("authorized", result.status)
        except RecoveryAttemptBlocked:
            return ("blocked", None)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(authorize, range(2)))
        assert sorted(outcome[0] for outcome in outcomes) == ["authorized", "blocked"]
        state = journals[0].get("boot-race")
        assert state.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        assert state.attempt_count == 1
        assert state.authorized_by in {"operator-0", "operator-1"}
    finally:
        for journal in journals:
            journal.close()


def test_only_one_connection_can_consume_retry_authorization(tmp_path):
    database = tmp_path / "attempts.sqlite"
    setup = EventLogRecoveryAttemptStore(database)
    first = setup.begin_attempt("boot-consume", "first attempt", checkpoint_fingerprint="sha256-a")
    setup.finish_failure("boot-consume", "simulated failure", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token)
    setup.authorize_retry("boot-consume", operator="operator", reason="reviewed")
    setup.close()

    journals = [EventLogRecoveryAttemptStore(database) for _ in range(2)]
    barrier = Barrier(2)

    def begin(index):
        barrier.wait(timeout=3)
        try:
            result = journals[index].begin_attempt(
                "boot-consume", "approved retry", checkpoint_fingerprint="sha256-a",
            )
            return ("started", result.attempt_count)
        except RecoveryAttemptBlocked:
            return ("blocked", None)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(begin, range(2)))
        assert sorted(outcome[0] for outcome in outcomes) == ["blocked", "started"]
        assert journals[0].get("boot-consume").attempt_count == 2
        assert journals[0].get("boot-consume").status is RecoveryAttemptStatus.IN_PROGRESS
    finally:
        for journal in journals:
            journal.close()


def test_only_one_connection_can_finish_an_attempt(tmp_path):
    database = tmp_path / "attempts.sqlite"
    setup = EventLogRecoveryAttemptStore(database)
    first = setup.begin_attempt("boot-finish", "attempt")
    setup.close()

    journals = [EventLogRecoveryAttemptStore(database) for _ in range(2)]
    barrier = Barrier(2)

    def finish(index):
        barrier.wait(timeout=3)
        try:
            result = (journals[index].finish_success("boot-finish", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token) if index == 0
                      else journals[index].finish_failure("boot-finish", "competing failure", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token))
            return ("finished", result.status)
        except RecoveryAttemptBlocked:
            return ("blocked", None)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(finish, range(2)))
        assert sorted(outcome[0] for outcome in outcomes) == ["blocked", "finished"]
        assert journals[0].get("boot-finish").status in {
            RecoveryAttemptStatus.SUCCEEDED, RecoveryAttemptStatus.FAILED,
        }
    finally:
        for journal in journals:
            journal.close()
