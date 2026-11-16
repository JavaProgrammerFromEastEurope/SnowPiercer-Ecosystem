"""Evidence-only SIGKILL-supervisor negative control, with INDEPENDENT cleanup.

The probe itself is a Linux subreaper. A real SIGKILL is sent to the
supervisor. It measures that its runner and detached child can remain alive
until this *separate* probe (representing an OS lifecycle authority) kills
and reaps them. No claim of automatic supervisor-self cleanup is permitted.
"""
from __future__ import annotations

import ctypes
import errno
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from scripts.ci.process_supervisor_v105 import _proc_table, _kill_identity


def main() -> int:
    ROOT = Path(__file__).resolve().parents[2]
    OUT = ROOT / 'AUDIT/evidence_v105'
    OUT.mkdir(exist_ok=True, parents=True)
    report_path = OUT / 'SUPERVISOR_SELF_SIGKILL_NEGATIVE_CONTROL.json'
    result = {'schema':'trainos.supervisor-selfkill-negative.v105', 'status':'FAIL', 'events': []}
    sup = None
    rootpid = childpid = None
    recorded = {}
    path = None
    try:
        if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
            raise RuntimeError('cannot become independent subreaper')
        with tempfile.TemporaryDirectory(prefix='trainos-v105-') as td:
            path = Path(td) / 'childpid'
            script = ('import subprocess,sys,time,pathlib;'
                      'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],'
                      'start_new_session=True);'
                      f'pathlib.Path({str(path)!r}).write_text(str(p.pid));time.sleep(60)')
            sup = subprocess.Popen([sys.executable,'-m','scripts.ci.process_supervisor_v105',
                                    '--timeout','20','--',sys.executable,'-c',script],
                                   cwd=ROOT, stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                   start_new_session=True)
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                table = _proc_table()
                roots = [pid for pid, data in table.items() if data[0] == sup.pid]
                if roots and path.exists() and path.stat().st_size:
                    rootpid = roots[0]
                    childpid = int(path.read_text())
                    recorded = {pid: table[pid][2] for pid in (rootpid, childpid)}
                    break
                time.sleep(0.025)
            if rootpid is None or childpid is None:
                raise RuntimeError('runner or child readiness missing')
            os.kill(sup.pid, signal.SIGKILL)
            result['supervisor_exitcode'] = sup.wait(timeout=5)
            time.sleep(0.15)
            table = _proc_table()
            root_live = rootpid in table and table[rootpid][1] != 'Z' and table[rootpid][2] == recorded[rootpid]
            child_live = childpid in table and table[childpid][1] != 'Z' and table[childpid][2] == recorded[childpid]
            result.update({'runner_survived_supervisor_kill': bool(root_live),
                           'detached_child_survived_supervisor_kill': bool(child_live),
                           'supervisor_selfkill_not_contained_without_external_authority':bool(root_live and child_live)})
            result['events'].append('independent_subreaper_begins_cleanup')
            for pid, start in recorded.items():
                _kill_identity(pid, start, signal.SIGKILL)
            deadline = time.monotonic()+4
            while time.monotonic()<deadline:
                try:
                    while True:
                        pid,status = os.waitpid(-1,os.WNOHANG)
                        if not pid:break
                except ChildProcessError:
                    pass
                table = _proc_table()
                live = [pid for pid, start in recorded.items() if pid in table and table[pid][1] != 'Z' and table[pid][2] == start]
                if not live: break
                time.sleep(0.05)
            table = _proc_table()
            residual = [pid for pid, start in recorded.items() if pid in table and table[pid][1] != 'Z' and table[pid][2] == start]
            result['residual_after_independent_cleanup'] = residual
            result['status'] = 'PASS' if root_live and child_live and not residual and result['supervisor_exitcode']==-9 else 'FAIL'
    except Exception as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
    finally:
        for pid in (childpid,rootpid):
            if pid:
                try:
                    if pid in recorded:_kill_identity(pid, recorded[pid], signal.SIGKILL)
                except Exception:
                    pass
        if sup is not None and sup.poll() is None:
            sup.kill()
            sup.wait()
        try:
            while True:
                pid,_ = os.waitpid(-1,os.WNOHANG)
                if not pid:break
        except ChildProcessError:
            pass
        report_path.write_text(json.dumps(result,indent=2)+'\n')
    return 0 if result['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
