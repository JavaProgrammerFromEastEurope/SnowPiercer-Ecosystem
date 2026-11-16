import os
import signal
import sys
import time
from pathlib import Path

import pytest

from tests.kernel_runner.runner import KernelTestRunner


def test_runner_success_and_failure():
    runner = KernelTestRunner()
    assert runner._execute([sys.executable, '-c', 'print("ok")']) == 0
    assert runner._execute([sys.executable, '-c', 'import sys;sys.exit(7)']) == 7


def test_runner_timeout_kills_descendants(tmp_path, monkeypatch):
    if os.name != 'posix':
        pytest.skip('POSIX process-group semantics required')
    pidfile = tmp_path / 'child.pid'
    code = ('import subprocess,sys,time;'
            'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(120)"]);'
            f'__import__("pathlib").Path({str(pidfile)!r}).write_text(str(p.pid));'
            'time.sleep(120)')
    monkeypatch.setenv('TRAINOS_KERNEL_FILE_TIMEOUT', '2')
    monkeypatch.setenv('TRAINOS_KERNEL_KILL_GRACE', '0.2')
    runner = KernelTestRunner()
    assert runner._execute([sys.executable, '-c', code]) == 124
    assert pidfile.exists()
    pid = int(pidfile.read_text())
    # Signal delivery/reparenting are asynchronous on loaded workers.
    # Preserve the strict non-running requirement using a bounded poll.
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        stat = Path(f'/proc/{pid}/stat')
        if not stat.exists() or stat.read_text().split()[2] == 'Z':
            break
        time.sleep(0.025)
    else:
        pytest.fail(f'descendant {pid} still executing after bounded cleanup')


def test_runner_invalid_timeout(monkeypatch):
    monkeypatch.setenv('TRAINOS_KERNEL_FILE_TIMEOUT', '0')
    with pytest.raises(ValueError):
        KernelTestRunner()
