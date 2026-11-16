"""Live SIGTERM-ignoring Runner: escalation and cleanup evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'AUDIT'/'evidence_v104'


def _wait_for(path, timeout=10):
    limit=time.monotonic()+timeout
    while time.monotonic()<limit:
        if path.is_file() and path.stat().st_size:
            return True
        time.sleep(.04)
    return False


def main():
    with tempfile.TemporaryDirectory(prefix='trainos-v104-escalation-') as temp:
        pidfile=Path(temp)/'runner.pid'
        code=("import pathlib,os,signal,time;"
              "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
              f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()));"
              "time.sleep(60)")
        rep=EV/'TERM_ESCALATION_SUPERVISOR_V104.json'
        out=EV/'TERM_ESCALATION_V104.stdout.log'
        err=EV/'TERM_ESCALATION_V104.stderr.log'
        with out.open('wb') as fout,err.open('wb') as ferr:
            proc=subprocess.Popen([sys.executable,'-m','scripts.ci.process_supervisor_v104',
                                    '--grace','0.5','--report',str(rep),'--',sys.executable,'-c',code],
                                   cwd=ROOT,stdout=fout,stderr=ferr,start_new_session=True)
            try:
                if not _wait_for(pidfile):
                    raise RuntimeError('Ignoring runner did not write PID')
                os.kill(proc.pid,signal.SIGTERM)
                rc=proc.wait(timeout=12)
                supervisor=json.loads(rep.read_text())
                status=('PASS' if rc==143 and supervisor.get('cleanup_complete') and
                        supervisor.get('supervisor_signal')==15 and
                        supervisor.get('runner_exitcode')==-9 else 'FAIL')
                summary={'schema':'trainos.v104.term-escalation.v1','runner_pid':int(pidfile.read_text()),
                         'wrapper_exitcode':rc,'runner_exitcode':supervisor['runner_exitcode'],
                         'supervisor_exitcode':supervisor['supervisor_exitcode'],
                         'cleanup_complete':supervisor['cleanup_complete'],
                         'test_status':status,'note':'SIGTERM ignored by runner; independent wrapper escalated to SIGKILL'}
                (EV/'TERM_ESCALATION_PROBE_V104.json').write_text(json.dumps(summary,indent=2)+'\n')
                (EV/'TERM_ESCALATION_V104.exitcode').write_text('0\n' if status=='PASS' else '1\n')
                print(json.dumps(summary,indent=2))
                return 0 if status=='PASS' else 1
            finally:
                if proc.poll() is None:
                    proc.kill();proc.wait()


if __name__=='__main__':
    raise SystemExit(main())
