"""Actual SIGKILL-supervisor/double-fork negative control with independent cleanup.

Shows why subreaper-only supervision is NOT cgroup containment. The probe is
itself a subreaper, uses pidfd process identities and reaps both subprocesses.
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

from scripts.ci.process_supervisor_v105 import _proc_table, _kill_identity

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'AUDIT/evidence_v106'


def main() -> int:
    OUT.mkdir(exist_ok=True, parents=True)
    result = {'schema':'trainos.doublefork-supervisor-sigkill-negative.v106',
              'status':'FAIL', 'events':[], 'independent_cleanup':False,
              'cgroup_kill_tested':False}
    supervisor = None
    identities = {}
    try:
        if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
            raise RuntimeError('independent subreaper unavailable')
        with tempfile.TemporaryDirectory(prefix='trainos-v106-doublefork-') as tmp:
            marker = Path(tmp) / 'grandchild.pid'
            script = ("import os,pathlib,time;"
                      "p=os.fork();"
                      "os.waitpid(p,0) if p else None;"
                      "os._exit(0) if p==0 and os.fork() else None;"
                      f"pathlib.Path({str(marker)!r}).write_text(str(os.getpid())) if p==0 else None;"
                      "time.sleep(60)")
            # Fork stage #1 uses a fresh session, its stage #2 forks then exits.
            # A Popen intermediate ensures no accidental ancestor assumption.
            runner_code = ('import subprocess,sys,time;'
                           'subprocess.Popen([sys.executable,"-c",'+repr(script)+'],start_new_session=True);'
                           'time.sleep(60)')
            supervisor = subprocess.Popen([sys.executable,'-m','scripts.ci.process_supervisor_v105',
                                           '--timeout','20','--',sys.executable,'-c',runner_code],
                                          cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                          start_new_session=True)
            deadline = time.monotonic()+8
            while time.monotonic()<deadline:
                table=_proc_table()
                runner = [p for p,data in table.items() if data[0]==supervisor.pid]
                if marker.exists() and runner:
                    grandchild=int(marker.read_text())
                    if grandchild in table and table[grandchild][1]!='Z':
                        identities={pid:table[pid][2] for pid in (runner[0],grandchild)}
                        result['runner_pid'],result['grandchild_pid']=runner[0],grandchild
                        break
                time.sleep(0.03)
            if len(identities)!=2:
                raise RuntimeError('double fork readiness failed')
            os.kill(supervisor.pid,signal.SIGKILL)
            result['supervisor_exitcode']=supervisor.wait(timeout=5)
            time.sleep(0.12)
            table=_proc_table()
            alive=[pid for pid,start in identities.items() if pid in table and table[pid][2]==start and table[pid][1]!='Z']
            result['running_after_supervisor_sigkill']=alive
            result['events'].append('actual supervisor SIGKILL; OS cgroup containment absent')
            for pid,start in identities.items():
                _kill_identity(pid,start,signal.SIGKILL)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                while True:
                    try:
                        pid,_=os.waitpid(-1,os.WNOHANG)
                        if not pid:break
                    except ChildProcessError:break
                table=_proc_table()
                residual=[pid for pid,start in identities.items()
                          if pid in table and table[pid][2]==start and table[pid][1]!='Z']
                if not residual:break
                time.sleep(0.03)
            result['residual_after_independent_cleanup']=residual
            result['independent_cleanup']=not bool(residual)
            result['status']='PASS_NEGATIVE_CONTROL' if (
                len(alive)==2 and not residual and result['supervisor_exitcode']==-9) else 'FAIL'
    except Exception as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
    finally:
        for pid,start in identities.items():
            _kill_identity(pid,start,signal.SIGKILL)
        if supervisor is not None and supervisor.poll() is None:
            supervisor.kill()
            supervisor.wait(timeout=3)
        while True:
            try:
                pid,_=os.waitpid(-1,os.WNOHANG)
                if not pid:break
            except ChildProcessError:break
        (OUT/'DOUBLEFORK_SUPERVISOR_SIGKILL_V106.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0 if result['status']=='PASS_NEGATIVE_CONTROL' else 1


if __name__=='__main__':
    raise SystemExit(main())
