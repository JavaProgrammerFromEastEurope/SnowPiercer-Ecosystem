"""Controlled Linux-only negative test for SIGKILL of the *runner* leader.

Records a gap in process-group cleanup, then forcibly cleans and reaps the
isolated child itself. A PASS outcome of this probe is NOT a safety PASS.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'AUDIT' / 'evidence_v103' / 'runner_sigkill_boundary.json'


def running(pid: int) -> bool:
    stat = Path('/proc') / str(pid) / 'stat'
    try:
        return stat.read_text().split()[2] not in ('Z', 'X')
    except FileNotFoundError:
        return False


def main() -> int:
    if not sys.platform.startswith('linux'):
        raise SystemExit('Linux-only probe; production capability not established')
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise SystemExit('PR_SET_CHILD_SUBREAPER not available')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {'schema': 'trainos.runner-sigkill-boundary.v103',
                                 'supervisor_mode': 'Linux PR_SET_CHILD_SUBREAPER',
                                 'status': 'NOT_EXECUTED'}
    with tempfile.TemporaryDirectory() as td:
        pidfile = Path(td) / 'child_pid'
        runner_script = ("import sys,pathlib;"
                         "from tests.kernel_runner.runner import KernelTestRunner;"
                         "KernelTestRunner()._execute([sys.executable, '-c', "
                         + repr('import time,os,pathlib;pathlib.Path('+repr(str(pidfile))+').write_text(str(os.getpid()));time.sleep(60)')
                         + "])")
        proc = subprocess.Popen([sys.executable, '-c', runner_script], cwd=ROOT,
                                start_new_session=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        pid = None
        try:
            deadline = time.monotonic()+10
            while time.monotonic() < deadline:
                if pidfile.is_file() and pidfile.stat().st_size:
                    pid = int(pidfile.read_text())
                    break
                if proc.poll() is not None:
                    break
                time.sleep(.02)
            if pid is None:
                report.update(status='SETUP_FAILED', runner_returncode=proc.poll())
                return 1
            report['child_pid'] = pid
            report['child_pgid_before_sigkill'] = os.getpgid(pid)
            report['child_running_before_sigkill'] = running(pid)
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
            report['runner_returncode_after_sigkill'] = proc.returncode
            report['child_running_after_runner_sigkill'] = running(pid)
            report['status'] = 'LIMITATION_CONFIRMED' if running(pid) else 'AUTOMATIC_CLEANUP_OBSERVED'
            return 0 if report['child_running_after_runner_sigkill'] else 1
        finally:
            if pid is not None:
                try:
                    os.killpg(pid, signal.SIGKILL)
                    report['cleanup_sigkill_sent'] = True
                except ProcessLookupError:
                    report['cleanup_sigkill_sent'] = False
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
            out, err = proc.communicate(timeout=5)
            report['runner_stdout'] = out.decode(errors='replace')[-3000:]
            report['runner_stderr'] = err.decode(errors='replace')[-3000:]
            if pid is not None:
                reaped = False
                deadline = time.monotonic() + 5
                while time.monotonic()<deadline:
                    try:
                        reaped_pid, _ = os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        reaped = not running(pid)
                        break
                    if reaped_pid == pid:
                        reaped = True
                        break
                    time.sleep(.02)
                report['child_reaped_by_probe_supervisor'] = reaped
                report['child_running_after_cleanup'] = running(pid)
            OUTPUT.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
