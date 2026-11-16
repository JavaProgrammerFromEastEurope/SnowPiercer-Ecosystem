"""End-to-end SIGKILL against an *actual* TrainOS Kernel Runner with live pytest."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from scripts.ci.process_supervisor_v104 import _proc_table

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'AUDIT'/'evidence_v104'


def alive(pid):
    table=_proc_table()
    return pid in table and table[pid][1] not in {'Z','X'}


def main():
    report=EV/'ACTUAL_KERNEL_SIGKILL_SUPERVISOR_V104.json'
    outfile=EV/'ACTUAL_KERNEL_SIGKILL.stdout.log'
    errfile=EV/'ACTUAL_KERNEL_SIGKILL.stderr.log'
    env=dict(os.environ,PYTHONWARNINGS='error::ResourceWarning,error::DeprecationWarning',
             PYTEST_ADDOPTS=f'-c {ROOT / "pytest.ini"}',PYTHONUNBUFFERED='1',
             TRAINOS_KERNEL_WORKERS='1', TRAINOS_KERNEL_BATCH='0')
    with outfile.open('wb') as stdout, errfile.open('wb') as stderr:
        sup=subprocess.Popen([sys.executable,'-m','scripts.ci.process_supervisor_v104',
                             '--report',str(report),'--timeout','120','--',sys.executable,
                             '-m','tests.kernel_runner'],cwd=ROOT,env=env,
                             stdout=stdout,stderr=stderr,start_new_session=True)
        runner_pid=None
        pytest_pid=None
        try:
            deadline=time.monotonic()+25
            while time.monotonic()<deadline and sup.poll() is None:
                table=_proc_table()
                root=[pid for pid,(ppid,st,ticks) in table.items() if ppid==sup.pid and st!='Z']
                if root:
                    runner_pid=root[0]
                    children=[pid for pid,(ppid,st,ticks) in table.items() if ppid==runner_pid and st!='Z']
                    if children:
                        pytest_pid=children[0]
                        break
                time.sleep(.025)
            if runner_pid is None or pytest_pid is None:
                raise RuntimeError('Did not observe real Kernel Runner and its pytest child')
            os.kill(runner_pid,signal.SIGKILL)
            rc=sup.wait(timeout=20)
            sup_report=json.loads(report.read_text())
            result={'schema':'trainos.v104.actual-kernel-sigkill.v1',
                    'kernel_runner_pid':runner_pid, 'pytest_child_pid':pytest_pid,
                    'supervisor_exitcode':rc, 'runner_exitcode':sup_report.get('runner_exitcode'),
                    'cleanup_complete':sup_report.get('cleanup_complete'),
                    'remaining_pytest_live':alive(pytest_pid),
                    'status':'PASS' if rc==137 and not alive(pytest_pid) and
                         sup_report.get('cleanup_complete') else 'FAIL'}
            (EV/'ACTUAL_KERNEL_SIGKILL_V104.json').write_text(json.dumps(result,indent=2)+'\n')
            (EV/'ACTUAL_KERNEL_SIGKILL.exitcode').write_text('0\n' if result['status']=='PASS' else '1\n')
            print(json.dumps(result,indent=2))
            return 0 if result['status']=='PASS' else 1
        finally:
            if sup.poll() is None:
                sup.send_signal(signal.SIGTERM)
                try: sup.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    sup.kill();sup.wait(timeout=5)


if __name__=='__main__':
    raise SystemExit(main())
