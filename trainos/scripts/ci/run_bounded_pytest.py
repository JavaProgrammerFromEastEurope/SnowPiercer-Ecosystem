"""Bounded pytest execution with durable evidence and POSIX group cleanup."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def _group_alive(pgid: int) -> bool:
    if os.name != 'posix':
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_group(pgid: int | None, proc: subprocess.Popen, sig: int, actions: list[str]) -> None:
    try:
        if pgid is not None:
            os.killpg(pgid, sig)
            actions.append('group_' + signal.Signals(sig).name.lower())
        elif proc.poll() is None:
            proc.send_signal(sig)
            actions.append('leader_' + signal.Signals(sig).name.lower())
    except ProcessLookupError:
        pass


def run_bounded(args: list[str], timeout: float, report: Path, grace: float = 3.0) -> int:
    if timeout <= 0 or grace < 0:
        raise ValueError('timeout must be positive and grace nonnegative')
    report.parent.mkdir(parents=True, exist_ok=True)
    stdout_path, stderr_path = report.with_suffix('.stdout.log'), report.with_suffix('.stderr.log')
    legacy_path = report.with_suffix('.pytest.log')
    command = [sys.executable, '-m', 'pytest', *args]
    started = time.monotonic()
    timed_out = False
    cleanup: list[str] = []
    returncode = None
    pgid = None
    error = None
    proc = None
    leader_reaped = False
    residual_group_after_leader = False
    try:
        with stdout_path.open('wb') as out, stderr_path.open('wb') as err:
            proc = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=(os.name == 'posix'))
            pgid = proc.pid if os.name == 'posix' else None
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                cleanup.append('timeout')
                _signal_group(pgid, proc, signal.SIGTERM, cleanup)
                try:
                    proc.wait(timeout=grace)
                except subprocess.TimeoutExpired:
                    _signal_group(pgid, proc, signal.SIGKILL, cleanup)
                    try:
                        proc.wait(timeout=max(grace, 0.5))
                    except subprocess.TimeoutExpired:
                        cleanup.append('leader_unreaped_after_sigkill')
            returncode = proc.poll()
            leader_reaped = returncode is not None
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        cleanup.append('runner_exception')
    finally:
        # A successful leader can leave workers alive. Terminate the entire session.
        if proc is not None and pgid is not None and _group_alive(pgid):
            residual_group_after_leader = not timed_out and proc.poll() is not None
            _signal_group(pgid, proc, signal.SIGTERM, cleanup)
            deadline = time.monotonic() + min(grace, 1.0)
            while _group_alive(pgid) and time.monotonic() < deadline:
                time.sleep(0.02)
            if _group_alive(pgid):
                _signal_group(pgid, proc, signal.SIGKILL, cleanup)
                deadline = time.monotonic() + 0.5
                while _group_alive(pgid) and time.monotonic() < deadline:
                    time.sleep(0.02)
        if proc is not None and proc.poll() is None:
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                cleanup.append('leader_still_alive')
        if proc is not None:
            returncode = proc.poll()
            leader_reaped = returncode is not None
        group_absent = pgid is not None and not _group_alive(pgid)
        if group_absent:
            cleanup.append('group_absent')
        if stdout_path.exists():
            shutil.copyfile(stdout_path, legacy_path)
        status = ('timeout' if timed_out else 'failed' if returncode != 0 or error or
                  (pgid is not None and not group_absent) or residual_group_after_leader else 'passed')
        result = {'schema': 'trainos.bounded-pytest.v2', 'command': command,
                  'timeout_seconds': timeout, 'duration_seconds': round(time.monotonic()-started, 3),
                  'status': status, 'timed_out': timed_out, 'returncode': returncode,
                  'stdout': str(stdout_path), 'stderr': str(stderr_path),
                  'group_cleanup': cleanup, 'group_absence_verified': group_absent,
                  'leader_reaped': leader_reaped,
                  'unexpected_residual_group': residual_group_after_leader,
                  'runner_error': error}
        temporary = report.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        temporary.replace(report)
    if timed_out:
        return 124
    if error or residual_group_after_leader or (pgid is not None and not group_absent):
        return 125
    return returncode if returncode is not None else 125


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--grace', type=float, default=3)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)
    args = ns.pytest_args[1:] if ns.pytest_args[:1] == ['--'] else ns.pytest_args
    if not args:
        parser.error('provide pytest arguments after --')
    return run_bounded(args, ns.timeout, ns.report, ns.grace)

if __name__ == '__main__':
    raise SystemExit(main())
