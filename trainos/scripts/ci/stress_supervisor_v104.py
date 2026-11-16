"""Five real SIGKILL probes for detached process fan-out, with JSON evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from scripts.ci.process_supervisor_v104 import _proc_table

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'AUDIT' / 'evidence_v104'


def _wait(predicate,timeout=12):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate(): return True
        time.sleep(0.04)
    return predicate()


def _not_running(pid):
    stat=Path(f'/proc/{pid}/stat')
    try:
        return not stat.exists() or stat.read_text().split()[2]=='Z'
    except FileNotFoundError:
        return True


def run(iteration,fanout=8):
    with tempfile.TemporaryDirectory(prefix='trainos-v104-stress-') as t:
        pidfile=Path(t)/'pids.json'
        report=OUT/f'sigkill_fanout_{iteration}.supervisor.json'
        out=OUT/f'sigkill_fanout_{iteration}.stdout.log'
        err=OUT/f'sigkill_fanout_{iteration}.stderr.log'
        code=("import subprocess,sys,time,json,pathlib;"
              f"p=[subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True) for _ in range({fanout})];"
              f"pathlib.Path({str(pidfile)!r}).write_text(json.dumps([c.pid for c in p]));time.sleep(60)")
        with out.open('wb') as fo,err.open('wb') as fe:
            proc=subprocess.Popen([sys.executable,'-m','scripts.ci.process_supervisor_v104',
                                   '--report',str(report),'--timeout','30','--',
                                   sys.executable,'-c',code],cwd=ROOT, stdout=fo,stderr=fe,
                                   start_new_session=True)
            try:
                if not _wait(lambda: pidfile.exists() and bool(pidfile.read_text())):
                    raise RuntimeError('Child PID list never created')
                pids=json.loads(pidfile.read_text())
                ptable=_proc_table()
                runner=[pid for pid,(parent,state,start) in ptable.items() if parent==proc.pid]
                if len(runner)!=1: raise RuntimeError(f'Expected one runner: {runner}')
                os.kill(runner[0],signal.SIGKILL)
                code=proc.wait(timeout=30)
                record=json.loads(report.read_text())
                killed=set(x['pid'] for x in record['events'] if x['event']=='signal_descendant')
                alive=[pid for pid in pids if not _not_running(pid)]
                result={'iteration':iteration,'fanout':fanout,'runner_pid':runner[0],
                        'detached_pids':pids,'signalled_pids':sorted(killed),
                        'unreaped_live':alive,'supervisor_exitcode':code,
                        'reported_cleanup':record['cleanup_complete'],
                        'result':'PASS' if code==137 and not alive and record['cleanup_complete'] and len(killed.intersection(pids))==fanout else 'FAIL'}
                (OUT/f'sigkill_fanout_{iteration}.json').write_text(json.dumps(result,indent=2)+'\n')
                (OUT/f'sigkill_fanout_{iteration}.exitcode').write_text('0\n' if result['result']=='PASS' else '1\n')
                return result
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                if pidfile.exists():
                    for pid in json.loads(pidfile.read_text()):
                        if not _not_running(pid):
                            try: os.kill(pid,signal.SIGKILL)
                            except ProcessLookupError: pass


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[run(i) for i in range(1,6)]
    (OUT/'SIGKILL_FANOUT_STRESS_SUMMARY_V104.json').write_text(json.dumps(results,indent=2)+'\n')
    for x in results: print(x['iteration'],x['result'],len(x['signalled_pids']),x['supervisor_exitcode'])
    return 0 if all(x['result']=='PASS' for x in results) else 1

if __name__=='__main__':
    raise SystemExit(main())
