"""Actual SIGTERM/SIGKILL runner tests with detached descendants and pidfd."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from scripts.ci.process_supervisor_v105 import _proc_table, _kill_identity

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'AUDIT/evidence_v107'
SUP=[sys.executable,'-m','scripts.ci.process_supervisor_v105']


def case(signum, case_name):
    with tempfile.TemporaryDirectory(prefix='trainos-v107-runner-signal-') as directory:
        marker=Path(directory)/'child.pid'
        script=('import subprocess,sys,pathlib,time;'
                'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],'
                'start_new_session=True);'
                f'pathlib.Path({str(marker)!r}).write_text(str(p.pid));time.sleep(60)')
        report=OUT/f'RUNNER_{case_name}_SUPERVISOR_V107.json'
        supervisor=subprocess.Popen([*SUP,'--report',str(report),'--timeout','15',
                                      '--',sys.executable,'-c',script],cwd=ROOT,
                                    start_new_session=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        root=child=None
        root_start=child_start=None
        error=None
        try:
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                table=_proc_table()
                roots=[pid for pid,data in table.items() if data[0]==supervisor.pid]
                if marker.is_file() and roots:
                    root=roots[0];child=int(marker.read_text())
                    if child in table:
                        root_start=table[root][2];child_start=table[child][2];break
                time.sleep(0.025)
            if root_start is None:raise RuntimeError('readiness missing')
            if not _kill_identity(root,root_start,signum):
                raise RuntimeError('pidfd signal failed')
            stdout,stderr=supervisor.communicate(timeout=15)
            data=json.loads(report.read_text())
            table=_proc_table()
            child_live=bool(child in table and table[child][2]==child_start and table[child][1]!='Z')
            expected=128+signum
            status='PASS' if (supervisor.returncode==expected and
                 data.get('cleanup_complete') and not child_live) else 'FAIL'
        except Exception as exc:
            error=f'{type(exc).__name__}: {exc}'
            status='FAIL'
            if supervisor.poll() is None:
                supervisor.terminate()
                try:supervisor.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    supervisor.kill();supervisor.wait(timeout=3)
            stdout,stderr=supervisor.communicate(timeout=5)
        finally:
            if child is not None and child_start is not None:
                _kill_identity(child,child_start,signal.SIGKILL)
            if root is not None and root_start is not None:
                _kill_identity(root,root_start,signal.SIGKILL)
            if supervisor.poll() is None:
                supervisor.kill();supervisor.wait(timeout=3)
        (OUT/f'runner_{case_name}.stdout.log').write_bytes(stdout)
        (OUT/f'runner_{case_name}.stderr.log').write_bytes(stderr)
        (OUT/f'runner_{case_name}.exitcode').write_text(f'{supervisor.returncode}\n')
        return {'case':case_name,'runner_signal':signum,'supervisor_exitcode':supervisor.returncode,
                'runner_pid':root,'detached_child_pid':child,
                'status':status,'error':error}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[case(signal.SIGTERM,'sigterm'),case(signal.SIGKILL,'sigkill')]
    payload={'schema':'trainos.v107-runner-signal-probes','results':results,
             'status':'PASS' if all(x['status']=='PASS' for x in results) else 'FAIL',
             'production_containment_proved':False}
    (OUT/'RUNNER_SIGNAL_PROBES_V107.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,indent=2))
    return 0 if payload['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
