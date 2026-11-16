"""v104 independent external supervisor: real process boundaries on Linux."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[3]
SUP = [sys.executable, '-m', 'scripts.ci.process_supervisor_v104']


def _not_running(pid):
    stat = Path(f'/proc/{pid}/stat')
    if stat.exists():
        return stat.read_text().split()[2] == 'Z'
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def _wait(condition, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.04)
    return condition()


def _start(tmp_path, code, *, timeout=20):
    report = tmp_path / 'supervisor.json'
    proc = subprocess.Popen(SUP + ['--report', str(report), '--timeout', str(timeout), '--',
                                   sys.executable, '-c', code], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    return proc, report


def _finish(proc, report):
    try:
        stdout, stderr = proc.communicate(timeout=25)
        assert report.exists(), (stdout, stderr)
        return json.loads(report.read_text()), stdout, stderr
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=3)


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux subreaper')
def test_normal_success_and_exit_code_propagation(tmp_path):
    for code, expected in [('print(1)', 0), ('import sys;sys.exit(7)', 7)]:
        p, r = _start(tmp_path, code)
        report, out, err = _finish(p, r)
        assert p.returncode == expected, (out, err)
        assert report['runner_exitcode'] == expected
        assert report['cleanup_complete']
        assert report['cgroup_v2']


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux subreaper')
def test_killed_runner_detached_descendant_cleanup(tmp_path):
    pidfile = tmp_path / 'detached.pid'
    child_code = "import os,time;time.sleep(60)"
    code = ("import subprocess,sys,time,pathlib;"
            f"p=subprocess.Popen([sys.executable,'-c',{child_code!r}],start_new_session=True);"
            f"pathlib.Path({str(pidfile)!r}).write_text(str(p.pid));time.sleep(60)")
    p, r = _start(tmp_path, code)
    try:
        assert _wait(lambda: pidfile.exists() and pidfile.stat().st_size > 0)
        pid = int(pidfile.read_text())
        # The test kills the Runner, NOT the supervisor (independent authority).
        from scripts.ci.process_supervisor_v104 import _proc_table
        sup_children = [child_pid for child_pid, (ppid, state, ticks) in _proc_table().items()
                        if ppid == p.pid]
        assert sup_children, 'Supervisor must have spawned a runner'
        os.kill(sup_children[0], signal.SIGKILL)
        report, out, err = _finish(p, r)
        assert p.returncode == 137, (report, out, err)
        assert report['cleanup_complete'] and report['observed_descendant_count'] >= 1
        assert _wait(lambda: _not_running(pid)), pid
        assert any(e['event'] == 'signal_descendant' and e['pid'] == pid for e in report['events'])
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux subreaper')
def test_normal_exit_with_detached_orphan_is_fail_closed(tmp_path):
    pidfile = tmp_path / 'orphan.pid'
    code = ("import subprocess,sys,pathlib;"
            "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True);"
            f"pathlib.Path({str(pidfile)!r}).write_text(str(p.pid))")
    p, r = _start(tmp_path, code)
    try:
        report, out, err = _finish(p, r)
        assert p.returncode == 125, (report, out, err)
        assert report['runner_exitcode'] == 0
        assert report['residual_at_runner_exit']
        assert report['cleanup_complete']
        assert _wait(lambda: _not_running(int(pidfile.read_text())))
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux subreaper')
def test_supervisor_timeout_is_bounded(tmp_path):
    p, r = _start(tmp_path, 'import time;time.sleep(60)', timeout=0.35)
    report, out, err = _finish(p, r)
    assert p.returncode == 124, (report, out, err)
    assert report['timeout'] and report['cleanup_complete']


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux subreaper')
def test_supervisor_sigterm_forwards_and_reaps(tmp_path):
    pidfile = tmp_path / 'runner.pid'
    code = f"import pathlib,os,time;pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()));time.sleep(60)"
    p, r = _start(tmp_path, code)
    assert _wait(lambda: pidfile.exists() and pidfile.stat().st_size > 0)
    pid = int(pidfile.read_text())
    os.kill(p.pid, signal.SIGTERM)
    report, out, err = _finish(p, r)
    assert p.returncode == 143, (report, out, err)
    assert report['supervisor_signal'] == signal.SIGTERM
    assert report['cleanup_complete']
    assert _wait(lambda: _not_running(pid))


def test_serial_default_preserves_ordered_fail_fast(monkeypatch):
    from tests.kernel_runner import runner as module
    from tests.kernel_runner.config import StageConfig
    monkeypatch.setenv('TRAINOS_KERNEL_WORKERS','1')
    monkeypatch.delenv('TRAINOS_KERNEL_BATCH', raising=False)
    monkeypatch.setattr(module,'STAGES',[StageConfig('a',['a','b','c']),StageConfig('b',['d'])])
    obj=module.KernelTestRunner()
    visited=[]
    def fake(file):
        visited.append(file)
        return 9 if file == 'b' else 0
    monkeypatch.setattr(obj,'_run_test',fake)
    assert obj.run()==1
    assert visited==['a','b']
    assert obj.failed==['b']
