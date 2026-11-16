"""Process-group boundary and warning-policy regressions for TrainOS v103."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.kernel_runner.runner import KernelTestRunner


def _not_running(pid):
    stat = Path(f'/proc/{pid}/stat')
    if stat.exists():
        return stat.read_text().split()[2] == 'Z'
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def _eventually_not_running(pid, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _not_running(pid):
            return True
        time.sleep(0.025)
    return _not_running(pid)


def _wait_for_file(path, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size:
            return int(path.read_text())
        time.sleep(0.02)
    raise AssertionError(f'PID file not created: {path}')


@pytest.mark.skipif(os.name != 'posix', reason='POSIX process groups')
def test_successful_leader_cannot_leave_residual_group(tmp_path):
    pidfile = tmp_path / 'residual.pid'
    code = ('import os,sys,pathlib;'
            'pid=os.fork();'
            'os.execl(sys.executable,sys.executable,"-c","import time;time.sleep(60)") if pid==0 else '
            f'pathlib.Path({str(pidfile)!r}).write_text(str(pid))')
    runner = KernelTestRunner()
    code = runner._execute([sys.executable, '-c', code])
    assert pidfile.exists()
    assert code == 125
    assert _eventually_not_running(int(pidfile.read_text()))


@pytest.mark.skipif(os.name != 'posix', reason='POSIX process groups')
def test_sigkill_of_subprocess_leader_cleans_descendants(tmp_path):
    pidfile = tmp_path / 'kill.pid'
    code = ('import os,sys,signal,pathlib;'
            'pid=os.fork();'
            'os.execl(sys.executable,sys.executable,"-c","import time;time.sleep(60)") if pid==0 else '
            f'pathlib.Path({str(pidfile)!r}).write_text(str(pid));'
            'os.kill(os.getpid(),signal.SIGKILL)')
    runner = KernelTestRunner()
    rc = runner._execute([sys.executable, '-c', code])
    assert rc != 0
    assert pidfile.exists()
    assert _eventually_not_running(int(pidfile.read_text()))


@pytest.mark.skipif(os.name != 'posix', reason='POSIX signals')
def test_sigterm_of_runner_reaps_its_test_process_group(tmp_path):
    pidfile = tmp_path / 'child.pid'
    wrapper = ("import sys;from tests.kernel_runner.runner import KernelTestRunner;"
               f"KernelTestRunner()._execute([sys.executable,'-c',"
               f"{'import os,time;open('+repr(str(pidfile))+',\"w\").write(str(os.getpid()));time.sleep(60)'!r}])")
    proc = subprocess.Popen([sys.executable, '-c', wrapper], start_new_session=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        test_pid = _wait_for_file(pidfile)
        os.kill(proc.pid, signal.SIGTERM)
        out, err = proc.communicate(timeout=8)
        assert proc.returncode == 128 + signal.SIGTERM, (out, err)
        assert _eventually_not_running(test_pid), (out, err)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=3)
        if pidfile.exists():
            try:
                os.killpg(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_timeout_policy_rejects_nan_and_infinity(monkeypatch):
    for value in ('nan', 'inf', '-inf'):
        monkeypatch.setenv('TRAINOS_KERNEL_FILE_TIMEOUT', value)
        with pytest.raises(ValueError):
            KernelTestRunner()


def test_legacy_kernel_runner_api_unchanged():
    from tests.kernel_runner.config import STAGES
    runner = KernelTestRunner()
    assert len(STAGES) == 24
    assert callable(runner.run)
    assert callable(runner._run_batch)
    assert callable(runner._run_test)
    assert callable(runner._expand)
