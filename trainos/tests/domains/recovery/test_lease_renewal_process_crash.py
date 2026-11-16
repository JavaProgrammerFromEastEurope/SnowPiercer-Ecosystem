"""Subprocess crash tests around the durable lease-renewal COMMIT boundary."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from kernel.command.events import EventLogRecoveryAttemptStore, RecoveryAttemptBlocked, RecoveryAttemptStatus


def _crash_worker(database: Path, mode: str, key: str, owner_run_id: str, fencing_token: int):
    script = r'''
import os, sys
from kernel.command.events import EventLogRecoveryAttemptStore

database, mode, key, owner_run_id, fencing_token = sys.argv[1:]
store = EventLogRecoveryAttemptStore(database)
raw = store._connection
class CrashAtCommit:
    def __getattr__(self, name):
        return getattr(raw, name)
    def commit(self):
        if mode == "before_commit":
            os._exit(74)
        raw.commit()
        os._exit(75)
store._connection = CrashAtCommit()
store.renew_lease(key, owner_run_id=owner_run_id,
                  fencing_token=int(fencing_token), lease_seconds=1200)
os._exit(0)
'''
    env = os.environ.copy()
    project_root = str(Path(__file__).resolve().parents[3])
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", script, str(database), mode, key, owner_run_id, str(fencing_token)],
        cwd=project_root, env=env, text=True, capture_output=True, timeout=15,
    )


@pytest.mark.parametrize(("mode", "exit_code", "renewal_committed"), [
    ("before_commit", 74, False),
    ("after_commit", 75, True),
])
def test_restart_reconciles_lease_state_after_process_crash(tmp_path, mode, exit_code, renewal_committed):
    database = tmp_path / f"{mode}.sqlite"
    setup = EventLogRecoveryAttemptStore(database)
    initial = setup.begin_attempt(f"stage117-{mode}", "stage117 process crash", lease_seconds=600)
    setup.close()

    child = _crash_worker(database, mode, initial.attempt_key, initial.owner_run_id, initial.fencing_token)
    assert child.returncode == exit_code, child.stderr

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        durable = restarted.get(initial.attempt_key)
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.IN_PROGRESS
        assert durable.owner_run_id == initial.owner_run_id
        assert durable.fencing_token == initial.fencing_token
        if renewal_committed:
            assert durable.lease_expires_at != initial.lease_expires_at
        else:
            assert durable.lease_expires_at == initial.lease_expires_at

        # Restart must act on the durable snapshot, not replay an assumed transition.
        finished = restarted.finish_success(
            initial.attempt_key, owner_run_id=initial.owner_run_id,
            fencing_token=initial.fencing_token,
        )
        assert finished.status is RecoveryAttemptStatus.SUCCEEDED
        assert finished.owner_run_id is None
        assert finished.lease_expires_at is None
        with pytest.raises(RecoveryAttemptBlocked):
            restarted.finish_success(
                initial.attempt_key, owner_run_id=initial.owner_run_id,
                fencing_token=initial.fencing_token,
            )
        assert restarted.get(initial.attempt_key) == finished
    finally:
        restarted.close()
