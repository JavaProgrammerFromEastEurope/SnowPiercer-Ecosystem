"""Real v106 supervisor SIGTERM/timeout and legacy admission probes.

All processes are bounded; probes write stdout, stderr and actual exit codes.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from scripts.ci.process_supervisor_v105 import _proc_table

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'AUDIT/evidence_v107'


def _run(case: str, cmd: list[str], *, action=None, marker=None) -> dict:
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                            start_new_session=True)
    killed = False
    ready = None
    try:
        if marker is not None:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if marker.exists() and marker.stat().st_size:
                    ready = int(marker.read_text())
                    break
                time.sleep(0.025)
            if ready is None:raise RuntimeError('child never wrote readiness marker')
        if action:
            action(proc)
        stdout,stderr=proc.communicate(timeout=20)
        status='CAPTURED'
    except Exception as e:
        status=f'ERROR: {e}'
        if proc.poll() is None:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            killed=True
        stdout,stderr=proc.communicate(timeout=8)
    (OUT/f'{case}.stdout.log').write_bytes(stdout)
    (OUT/f'{case}.stderr.log').write_bytes(stderr)
    (OUT/f'{case}.exitcode').write_text(f'{proc.returncode}\n')
    return {'status':status,'command':cmd,'exitcode':proc.returncode,'readiness_pid':ready,
            'emergency_kill':killed,'stdout':f'{case}.stdout.log','stderr':f'{case}.stderr.log'}


def main() -> int:
    OUT.mkdir(parents=True,exist_ok=True)
    results={}
    with tempfile.TemporaryDirectory(prefix='trainos-v107-probe-') as d:
        marker=Path(d)/'ready.pid'
        report=OUT/'SIGTERM_SUPERVISOR_V107.json'
        code=f'import os,time,pathlib;pathlib.Path({str(marker)!r}).write_text(str(os.getpid()));time.sleep(60)'
        cmd=[sys.executable,'-m','scripts.ci.process_supervisor_v105','--report',str(report),
             '--timeout','15','--',sys.executable,'-c',code]
        results['sigterm']=_run('sigterm_supervisor',cmd,action=lambda proc:os.kill(proc.pid,signal.SIGTERM),marker=marker)
        if report.exists():
            data=json.loads(report.read_text())
            results['sigterm']['cleanup_complete']=data['cleanup_complete']
            results['sigterm']['supervisor_signal']=data['supervisor_signal']
        marker.unlink(missing_ok=True)
        report=OUT/'TIMEOUT_SUPERVISOR_V107.json'
        cmd=[sys.executable,'-m','scripts.ci.process_supervisor_v105','--report',str(report),
             '--timeout','0.35','--grace','0.15','--',sys.executable,'-c',
             'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)']
        results['timeout']=_run('timeout_supervisor',cmd)
        if report.exists():
            data=json.loads(report.read_text())
            results['timeout']['cleanup_complete']=data['cleanup_complete']
            results['timeout']['timeout']=data['timeout']
    # The legacy admission exercise must be run in a subprocess with its own environment.
    env=dict(os.environ,TRAINOS_KERNEL_PRODUCTION='1')
    p=subprocess.run([sys.executable,'-m','tests.kernel_runner'],cwd=ROOT,env=env,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8)
    (OUT/'legacy_production_denied.stdout.log').write_bytes(p.stdout)
    (OUT/'legacy_production_denied.stderr.log').write_bytes(p.stderr)
    (OUT/'legacy_production_denied.exitcode').write_text(f'{p.returncode}\n')
    results['legacy_admission']={'exitcode':p.returncode,
        'explicit_production_env':True,'refused_before_tests':b'admission unavailable' in p.stderr,
        'direct_dev_bypass_unrestricted':True}
    good=(results['sigterm']['exitcode']==143 and results['sigterm'].get('cleanup_complete')
          and results['timeout']['exitcode']==124 and results['timeout'].get('cleanup_complete')
          and results['legacy_admission']['exitcode']!=0 and results['legacy_admission']['refused_before_tests'])
    result={'schema':'trainos.v107.process-boundary','results':results,'status':'PASS' if good else 'FAIL'}
    (OUT/'PROCESS_BOUNDARY_PROBES_V107.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'exitcodes':{k:v['exitcode'] for k,v in results.items()}},indent=2))
    return 0 if good else 1

if __name__=='__main__':
    raise SystemExit(main())
