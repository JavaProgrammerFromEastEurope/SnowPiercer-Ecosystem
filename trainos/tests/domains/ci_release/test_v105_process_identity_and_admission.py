"""v105: kernel pidfd identity and fail-closed production admission contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from scripts.ci.process_supervisor_v105 import _kill_identity, _proc_table
from tests.kernel_runner.runner import KernelTestRunner

ROOT = Path(__file__).resolve().parents[3]
SUP = [sys.executable, '-m', 'scripts.ci.process_supervisor_v105']


def test_direct_production_runner_fails_closed(monkeypatch):
    monkeypatch.setenv('TRAINOS_KERNEL_PRODUCTION', '1')
    with pytest.raises(RuntimeError, match='admission unavailable'):
        KernelTestRunner()


def test_supervisor_production_fails_before_spawn(tmp_path):
    marker = tmp_path / 'must-not-exist'
    cmd = [*SUP, '--production', '--', sys.executable, '-c',
           f'from pathlib import Path;Path({str(marker)!r}).write_text("unexpected")']
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=8)
    assert result.returncode == 125
    assert 'production admission requires' in result.stderr
    assert not marker.exists()


@pytest.mark.skipif(sys.platform != 'linux' or not hasattr(os, 'pidfd_open') or
                    not hasattr(signal, 'pidfd_send_signal'), reason='Linux pidfd only')
def test_pidfd_identity_refuses_stale_observation_and_kills_matching_process():
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        pid, start = child.pid, _proc_table()[child.pid][2]
        assert _kill_identity(pid, start + 1, signal.SIGKILL) is False
        assert child.poll() is None
        assert _kill_identity(pid, start, signal.SIGKILL) is True
        assert child.wait(timeout=3) == -signal.SIGKILL
        assert not _kill_identity(pid, start, signal.SIGKILL)
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)


@pytest.mark.skipif(sys.platform != 'linux' or not hasattr(os, 'pidfd_open') or
                    not hasattr(signal, 'pidfd_send_signal'), reason='Linux pidfd only')
def test_v105_supervisor_cleans_detached_on_runner_sigkill(tmp_path):
    report = tmp_path / 'report.json'
    marker = tmp_path / 'ready.pid'
    code = ('import subprocess,sys,pathlib,time;'
            'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],'
            'start_new_session=True);'
            f'pathlib.Path({str(marker)!r}).write_text(str(child.pid));time.sleep(60)')
    supervisor = subprocess.Popen([*SUP, '--report', str(report), '--timeout', '15',
                                   '--', sys.executable, '-c', code],
                                  cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  start_new_session=True)
    try:
        deadline = time.monotonic() + 8
        childpid = None
        rootpid = None
        while time.monotonic() < deadline:
            table = _proc_table()
            roots = [pid for pid, data in table.items() if data[0] == supervisor.pid]
            if marker.is_file() and marker.stat().st_size and roots:
                childpid = int(marker.read_text())
                rootpid = roots[0]
                break
            time.sleep(0.025)
        assert childpid is not None and rootpid is not None, 'runner readiness failed'
        os.kill(rootpid, signal.SIGKILL)
        stdout, stderr = supervisor.communicate(timeout=15)
        assert supervisor.returncode == 137, (stdout, stderr)
        data = json.loads(report.read_text())
        assert data['cleanup_complete'] and data['pidfd_available']
        assert any(e['event']=='signal_descendant' and e['pid']==childpid for e in data['events'])
        table = _proc_table()
        assert childpid not in table or table[childpid][1] == 'Z'
    finally:
        if supervisor.poll() is None:
            os.killpg(supervisor.pid, signal.SIGKILL)
            supervisor.wait(timeout=3)
        if marker.is_file():
            try:
                os.kill(int(marker.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
